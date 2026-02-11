"""Unified land-object fetcher for Riyadh parcels.

Takes a Parcel ID → calls Geoportal + SREM → returns a single
structured Land Object with geometry, zoning, regulations, and
market data.

Usage:
    python data_fetch.py 3710897
    python data_fetch.py 3710897 3710898   # multiple parcels
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from playwright.async_api import BrowserContext, async_playwright

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROXY = (
    "https://mapservice.alriyadh.gov.sa"
    "/APIGEOPORTALN/Handler/proxy.ashx"
)
PARCELS_SERVER = (
    "https://maps.alriyadh.gov.sa/gprtl/rest/services"
    "/WebMercator/WMParcelsLayerOne/MapServer"
)
BUILDING_REPORT_URL = (
    "https://mapservice.alriyadh.gov.sa"
    "/BuildingSystem/building-code-report-experimental"
    "?parcelId={pid}"
)
SREM_API = "https://prod-srem-api-srem.moj.gov.sa/api/v1/Dashboard"
REFERER = "https://mapservice.alriyadh.gov.sa/geoportal/geomap"

TOTAL_FIELDS = 25  # used for health-score calculation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("fetch")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _centroid(rings: list[list[list[float]]]) -> tuple[float, float]:
    """Compute the centroid of an ArcGIS polygon ring."""
    pts = rings[0]  # outer ring
    n = len(pts) - 1  # last point duplicates the first
    if n < 1:
        return 0.0, 0.0
    cx = sum(p[0] for p in pts[:n]) / n
    cy = sum(p[1] for p in pts[:n]) / n
    return cx, cy  # lng, lat


def _strip_jsonp(text: str) -> str:
    """Remove JSONP callback wrapper from a response."""
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return text
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return text[start:end]
    except ValueError:
        return text


def _parse_pdf_regulations(pdf_bytes: bytes) -> dict[str, Any]:
    """Extract regulation values from the BuildingSystem PDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text("text")
    doc.close()

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    cleaned = " ".join(lines)
    regs: dict[str, Any] = {}

    # Building code
    m = re.search(r"(\d{3})\s*([مس])", cleaned)
    if m:
        regs["building_code"] = f"{m.group(2)} {m.group(1)}"
    else:
        t = re.search(r"(T\d+[\s.]*\d*)", cleaned)
        if t:
            regs["building_code"] = t.group(1).strip()

    # Allowed uses
    use_map = {
        "ﺳﻜﻨﻲ": "residential", "سكني": "residential",
        "ﺗﺠﺎري": "commercial", "تجاري": "commercial",
        "ﻣﻜﺎﺗﺐ": "offices", "مكاتب": "offices",
        "ﻣﺨﺘﻠﻂ": "mixed_use", "مختلط": "mixed_use",
    }
    uses: list[str] = []
    in_uses = False
    for line in lines:
        if "اﻻﺳﺘﺨﺪاﻣﺎت" in line or "الاستخدامات" in line:
            in_uses = True
            continue
        if in_uses:
            if "اﻻرﺗﺪاد" in line or "الارتداد" in line:
                break
            for ar, en in use_map.items():
                if ar in line and en not in uses:
                    uses.append(en)
    regs["allowed_uses"] = uses

    # Floors
    if "أول" in cleaned and ("أرﴈ" in cleaned or "أرضي" in cleaned):
        regs["max_floors"] = 2
    elif "دورين" in cleaned:
        regs["max_floors"] = 2
    elif "ثلاث" in cleaned:
        regs["max_floors"] = 3
    elif "أربع" in cleaned:
        regs["max_floors"] = 4

    # FAR
    far_m = re.search(r"(?:ﻣﻌﺎﻣﻞ|معامل).*?(\d+\.\d+)", cleaned)
    if far_m:
        val = float(far_m.group(1))
        if 0.1 <= val <= 10:
            regs["far"] = val

    # Coverage
    cov = re.search(r"%(\d+)", cleaned)
    if cov:
        v = int(cov.group(1))
        if 20 <= v <= 100:
            regs["coverage_ratio"] = v / 100.0

    # Setbacks
    in_sb = False
    sb_lines: list[str] = []
    for line in lines:
        if "اﻻرﺗﺪادات" in line or "الارتدادات" in line:
            in_sb = True
            rest = re.sub(r"اﻻرﺗﺪادات|الارتدادات", "", line).strip()
            if rest:
                sb_lines.append(rest)
            continue
        if in_sb:
            if "اﻻرﺗﻔﺎﻋﺎت" in line or "الارتفاعات" in line:
                break
            sb_lines.append(line)
    if sb_lines:
        raw = " ".join(sb_lines)
        meters = re.findall(r"م(\d+\.?\d*)", raw)
        regs["setbacks_raw"] = raw
        if meters:
            regs["setback_values_m"] = [float(v) for v in meters]

    # Notes
    in_notes = False
    notes: list[str] = []
    for line in lines:
        if "اﻟﻤﻼﺣﻈﺎت" in line or "الملاحظات" in line:
            in_notes = True
            continue
        if in_notes:
            notes.append(line)
    if notes:
        full = " ".join(notes)
        items = re.split(r"\s*-\s*", full)
        regs["notes"] = [n.strip() for n in items if len(n.strip()) > 5][:10]

    regs["pdf_text"] = text
    return regs


# ---------------------------------------------------------------------------
# Step 1: Geoportal query
# ---------------------------------------------------------------------------

async def fetch_parcel_query(
    ctx: BrowserContext, parcel_id: int,
) -> dict[str, Any]:
    """Query the parcels MapServer for basic parcel data + geometry."""
    url = (
        f"{PROXY}?{PARCELS_SERVER}/2/query"
        f"?where=PARCELID%3D{parcel_id}"
        f"&returnGeometry=true"
        f"&outFields=*"
        f"&outSR=4326"
        f"&f=json"
    )
    resp = await ctx.request.get(
        url, headers={"Referer": REFERER}, timeout=15_000,
    )
    text = _strip_jsonp(await resp.text())
    data = json.loads(text)
    features = data.get("features", [])
    if not features:
        return {}
    feat = features[0]
    return {
        "attributes": feat.get("attributes", {}),
        "geometry": feat.get("geometry", {}),
    }


# ---------------------------------------------------------------------------
# Step 2: Geoportal identify
# ---------------------------------------------------------------------------

async def fetch_parcel_identify(
    ctx: BrowserContext, lng: float, lat: float,
) -> dict[str, Any]:
    """Identify at parcel centroid → decoded labels, district, etc."""
    url = (
        f"{PROXY}?{PARCELS_SERVER}/identify"
        f"?geometry={lng},{lat}"
        f"&geometryType=esriGeometryPoint"
        f"&sr=4326&tolerance=5"
        f"&mapExtent={lng - 0.001},{lat - 0.001},{lng + 0.001},{lat + 0.001}"
        f"&imageDisplay=1440,900,96"
        f"&layers=all:2"
        f"&returnGeometry=false"
        f"&f=json"
    )
    resp = await ctx.request.get(
        url, headers={"Referer": REFERER}, timeout=15_000,
    )
    data = json.loads(await resp.text())
    results = data.get("results", [])
    if not results:
        return {}
    return results[0].get("attributes", {})


# ---------------------------------------------------------------------------
# Step 3: Building regulation PDF
# ---------------------------------------------------------------------------

async def fetch_building_regulations(
    ctx: BrowserContext, parcel_id: int,
) -> dict[str, Any]:
    """Download the BuildingSystem PDF and parse regulation values."""
    url = BUILDING_REPORT_URL.format(pid=parcel_id)
    resp = await ctx.request.get(
        url, headers={"Referer": REFERER}, timeout=45_000,
    )
    body = await resp.body()
    if resp.status != 200 or len(body) < 500:
        return {"error": f"HTTP {resp.status}, {len(body)} bytes"}
    return _parse_pdf_regulations(body)


# ---------------------------------------------------------------------------
# Step 4: SREM market data
# ---------------------------------------------------------------------------

async def fetch_srem_market(
    ctx: BrowserContext, city_name: str | None = None,
) -> dict[str, Any]:
    """Get SREM public market indicators (no auth required)."""
    market: dict[str, Any] = {}

    # Market index
    try:
        r = await ctx.request.get(
            f"{SREM_API}/GetMarketIndex", timeout=10_000,
        )
        d = json.loads(await r.text())
        if d.get("IsSuccess"):
            market["market_index"] = d["Data"]["Index"]
            market["market_index_change"] = d["Data"]["Change"]
    except Exception as exc:
        log.warning("SREM index: %s", exc)

    # Trending districts
    try:
        r = await ctx.request.post(
            f"{SREM_API}/GetTrendingDistricts",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "periodCategory": "D",
                "citySerial": 0,
                "areaCategory": "A",
                "areaSerial": 0,
            }),
            timeout=10_000,
        )
        d = json.loads(await r.text())
        if d.get("IsSuccess"):
            market["trending_districts"] = d["Data"].get(
                "TrendingDistricts", [],
            )
    except Exception as exc:
        log.warning("SREM trending: %s", exc)

    # Area info (daily, national)
    try:
        r = await ctx.request.post(
            f"{SREM_API}/GetAreaInfo",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "periodCategory": "D",
                "period": 1,
                "areaSerial": 0,
                "areaType": "A",
                "cityCode": 0,
            }),
            timeout=10_000,
        )
        d = json.loads(await r.text())
        if d.get("IsSuccess"):
            stats = d["Data"].get("Stats", [])
            if stats:
                latest = stats[0]
                market["daily_total_count"] = latest.get("TotalCount")
                market["daily_total_price"] = latest.get("TotalPrice")
                market["daily_avg_price_sqm"] = latest.get("AveragePrice")
                market["daily_total_area"] = latest.get("TotalArea")
    except Exception as exc:
        log.warning("SREM area: %s", exc)

    return market


# ---------------------------------------------------------------------------
# Land Object assembly
# ---------------------------------------------------------------------------

# Land-use code lookup (from Geoportal identify results)
LAND_USE_LABELS = {
    1000: "سكني (Residential)",
    7500: "متعددة الإستخدام (Multi-use)",
    7510: "سكني - تجاري (Residential-Commercial)",
}


def build_land_object(
    parcel_id: int,
    query_data: dict,
    identify_data: dict,
    regulations: dict,
    srem_data: dict,
) -> dict[str, Any]:
    """Assemble the unified Land Object from all sources."""
    attrs = query_data.get("attributes", {})
    geom = query_data.get("geometry", {})
    rings = geom.get("rings", [])
    centroid_lng, centroid_lat = _centroid(rings) if rings else (0, 0)

    obj: dict[str, Any] = {
        "parcel_id": parcel_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),

        # --- Parcel identity ---
        "parcel_number": attrs.get("PARCELNO"),
        "plan_number": attrs.get("PLANNO"),
        "block_number": attrs.get("BLOCKNO"),
        "object_id": attrs.get("OBJECTID"),

        # --- Location ---
        "district_name": identify_data.get("الحي")
            or identify_data.get("DISTRICT"),
        "municipality": identify_data.get("البلديات الفرعية")
            or identify_data.get("SUBMUNICIPALITY"),
        "centroid": {"lng": centroid_lng, "lat": centroid_lat},
        "geometry": geom if geom else None,

        # --- Area ---
        "area_sqm": attrs.get("SHAPE.AREA"),

        # --- Zoning / land use ---
        "building_use_code": attrs.get("BUILDINGUSECODE"),
        "building_code_label": attrs.get("FLGBLDCODE")
            or identify_data.get("نظام البناء"),
        "primary_use_code": attrs.get("PARCELSUBTYPE"),
        "primary_use_label": identify_data.get("الاستخدام الرئيسي")
            or LAND_USE_LABELS.get(attrs.get("PARCELSUBTYPE")),
        "secondary_use_code": attrs.get("LANDUSEAGROUP"),
        "detailed_use_code": attrs.get("LANDUSEADETAILED"),
        "detailed_use_label": identify_data.get("استخدام الارض")
            or LAND_USE_LABELS.get(attrs.get("LANDUSEADETAILED")),
        "reviewed_bld_code": attrs.get("REVIEWED_BLD_CODE"),

        # --- Decoded regulations (from PDF) ---
        "regulations": {
            "max_floors": regulations.get("max_floors"),
            "far": regulations.get("far"),
            "coverage_ratio": regulations.get("coverage_ratio"),
            "allowed_uses": regulations.get("allowed_uses"),
            "setbacks_raw": regulations.get("setbacks_raw"),
            "setback_values_m": regulations.get("setback_values_m"),
            "notes": regulations.get("notes"),
        },

        # --- Market data (from SREM) ---
        "market": {
            "srem_market_index": srem_data.get("market_index"),
            "srem_index_change": srem_data.get("market_index_change"),
            "daily_total_transactions": srem_data.get("daily_total_count"),
            "daily_total_value_sar": srem_data.get("daily_total_price"),
            "daily_avg_price_sqm": srem_data.get("daily_avg_price_sqm"),
            "trending_districts": [
                {
                    "name": d.get("DistrictName"),
                    "city": d.get("CityName"),
                    "deals": d.get("TotalCount"),
                    "total_sar": d.get("TotalPrice"),
                }
                for d in srem_data.get("trending_districts", [])[:5]
            ],
        },

        # --- Data health ---
        "data_health": {},
    }

    # Compute health score
    populated = 0
    checked = 0
    fields_to_check = [
        "parcel_number", "plan_number", "district_name", "municipality",
        "area_sqm", "building_code_label", "primary_use_label",
        "detailed_use_label",
    ]
    for f in fields_to_check:
        checked += 1
        if obj.get(f):
            populated += 1

    reg = obj.get("regulations", {})
    reg_fields = ["max_floors", "far", "coverage_ratio", "allowed_uses"]
    for f in reg_fields:
        checked += 1
        val = reg.get(f)
        if val is not None and val != [] and val != "":
            populated += 1

    mkt = obj.get("market", {})
    mkt_fields = ["srem_market_index", "daily_avg_price_sqm"]
    for f in mkt_fields:
        checked += 1
        if mkt.get(f) is not None:
            populated += 1

    geo_check = 1 if rings else 0
    checked += 1
    populated += geo_check

    score = round(populated / checked * 100, 1) if checked > 0 else 0
    obj["data_health"] = {
        "fields_checked": checked,
        "fields_populated": populated,
        "score_pct": score,
        "missing": [
            f for f in fields_to_check if not obj.get(f)
        ] + [
            f"regulations.{f}" for f in reg_fields
            if reg.get(f) is None or reg.get(f) == []
        ] + [
            f"market.{f}" for f in mkt_fields
            if mkt.get(f) is None
        ] + (["geometry"] if not rings else []),
    }

    return obj


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def fetch_land_object(parcel_id: int) -> dict[str, Any]:
    """Fetch a complete Land Object for a given parcel ID."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(ignore_https_errors=True)

        try:
            # Step 1: Parcel query
            log.info("[%d] Step 1: MapServer query...", parcel_id)
            query_data = await fetch_parcel_query(ctx, parcel_id)
            attrs = query_data.get("attributes", {})
            geom = query_data.get("geometry", {})
            rings = geom.get("rings", [])
            if not attrs:
                log.warning("[%d] No parcel found in query.", parcel_id)

            # Step 2: Identify (needs centroid)
            identify_data: dict = {}
            if rings:
                lng, lat = _centroid(rings)
                log.info("[%d] Step 2: MapServer identify at (%.5f, %.5f)...", parcel_id, lng, lat)
                identify_data = await fetch_parcel_identify(ctx, lng, lat)
            else:
                log.warning("[%d] No geometry — skipping identify.", parcel_id)

            # Step 3: Building regulations PDF
            log.info("[%d] Step 3: Building regulation PDF...", parcel_id)
            try:
                regulations = await fetch_building_regulations(ctx, parcel_id)
            except Exception as exc:
                log.warning("[%d] PDF fetch failed: %s", parcel_id, exc)
                regulations = {"error": str(exc)}

            # Step 4: SREM market data
            log.info("[%d] Step 4: SREM market data...", parcel_id)
            srem_data = await fetch_srem_market(ctx)

            # Assemble
            log.info("[%d] Assembling land object...", parcel_id)
            land_obj = build_land_object(
                parcel_id, query_data, identify_data, regulations, srem_data,
            )

            # Remove raw PDF text from output (keep it lean)
            if "pdf_text" in land_obj.get("regulations", {}):
                del land_obj["regulations"]["pdf_text"]

            return land_obj

        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main(parcel_ids: list[int]) -> None:
    """Fetch land objects for one or more parcel IDs."""
    for pid in parcel_ids:
        log.info("=" * 60)
        log.info("Fetching parcel %d", pid)
        log.info("=" * 60)

        land_obj = await fetch_land_object(pid)

        # Save
        out_path = Path(f"test_land_object_{pid}.json")
        out_path.write_text(
            json.dumps(land_obj, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("Saved: %s", out_path)

        # Print summary
        health = land_obj.get("data_health", {})
        log.info("--- RESULT for %d ---", pid)
        log.info("  District: %s", land_obj.get("district_name"))
        log.info("  Building code: %s", land_obj.get("building_code_label"))
        log.info("  Area: %s m²", land_obj.get("area_sqm"))
        reg = land_obj.get("regulations", {})
        log.info("  Max floors: %s", reg.get("max_floors"))
        log.info("  FAR: %s", reg.get("far"))
        log.info("  Coverage: %s", reg.get("coverage_ratio"))
        log.info("  Allowed uses: %s", reg.get("allowed_uses"))
        log.info("  Market index: %s", land_obj.get("market", {}).get("srem_market_index"))
        log.info(
            "  Health: %s%% (%d/%d fields)",
            health.get("score_pct"),
            health.get("fields_populated"),
            health.get("fields_checked"),
        )
        if health.get("missing"):
            log.info("  Missing: %s", health["missing"])


if __name__ == "__main__":
    ids = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [3710897]
    asyncio.run(main(ids))
