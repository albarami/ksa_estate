"""Data fetcher using httpx (fast) + Playwright (PDF only).

Two-layer cache:
  Layer 1: Land Objects keyed by parcel_id (1h TTL)
  Layer 2: Decoded regulations keyed by BUILDINGUSECODE (24h TTL)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import fitz  # PyMuPDF
import httpx
from cachetools import TTLCache

log = logging.getLogger("data_fetch")

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
HEADERS = {"Referer": REFERER}

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------

_land_cache: TTLCache = TTLCache(maxsize=500, ttl=3600)       # 1 hour
_reg_cache: TTLCache = TTLCache(maxsize=200, ttl=86400)       # 24 hours
_srem_cache: TTLCache = TTLCache(maxsize=10, ttl=300)         # 5 min


def clear_caches() -> None:
    """Clear all caches (for testing)."""
    _land_cache.clear()
    _reg_cache.clear()
    _srem_cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _centroid(rings: list) -> tuple[float, float]:
    pts = rings[0]
    n = len(pts) - 1
    if n < 1:
        return 0.0, 0.0
    return sum(p[0] for p in pts[:n]) / n, sum(p[1] for p in pts[:n]) / n


def _strip_jsonp(text: str) -> str:
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return text
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return text[start:end]
    except ValueError:
        return text


LAND_USE_LABELS = {
    1000: "سكني (Residential)",
    7500: "متعددة الإستخدام (Multi-use)",
    7510: "سكني - تجاري (Residential-Commercial)",
}


# ---------------------------------------------------------------------------
# PDF parsing (same logic as validate_building_reports.py)
# ---------------------------------------------------------------------------

def _parse_pdf_regulations(pdf_bytes: bytes) -> dict[str, Any]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "".join(page.get_text("text") for page in doc)
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
        regs["setbacks_raw"] = raw
        meters = re.findall(r"م(\d+\.?\d*)", raw)
        if meters:
            regs["setback_values_m"] = [float(v) for v in meters]

    # Notes
    in_notes = False
    note_lines: list[str] = []
    for line in lines:
        if "اﻟﻤﻼﺣﻈﺎت" in line or "الملاحظات" in line:
            in_notes = True
            continue
        if in_notes:
            note_lines.append(line)
    if note_lines:
        full = " ".join(note_lines)
        items = re.split(r"\s*-\s*", full)
        regs["notes"] = [n.strip() for n in items if len(n.strip()) > 5][:10]

    return regs


# ---------------------------------------------------------------------------
# Step 1: Parcel query (httpx)
# ---------------------------------------------------------------------------

async def _fetch_parcel_query(
    client: httpx.AsyncClient, parcel_id: int,
) -> dict[str, Any]:
    url = (
        f"{PROXY}?{PARCELS_SERVER}/2/query"
        f"?where=PARCELID%3D{parcel_id}"
        f"&returnGeometry=true&outFields=*&outSR=4326&f=json"
    )
    resp = await client.get(url, headers=HEADERS, timeout=15)
    text = _strip_jsonp(resp.text)
    data = json.loads(text)
    features = data.get("features", [])
    if not features:
        return {}
    feat = features[0]
    return {"attributes": feat.get("attributes", {}), "geometry": feat.get("geometry", {})}


# ---------------------------------------------------------------------------
# Step 2: Identify (httpx)
# ---------------------------------------------------------------------------

async def _fetch_parcel_identify(
    client: httpx.AsyncClient, lng: float, lat: float,
) -> dict[str, Any]:
    url = (
        f"{PROXY}?{PARCELS_SERVER}/identify"
        f"?geometry={lng},{lat}"
        f"&geometryType=esriGeometryPoint&sr=4326&tolerance=5"
        f"&mapExtent={lng-0.001},{lat-0.001},{lng+0.001},{lat+0.001}"
        f"&imageDisplay=1440,900,96&layers=all:2"
        f"&returnGeometry=false&f=json"
    )
    resp = await client.get(url, headers=HEADERS, timeout=15)
    data = json.loads(resp.text)
    results = data.get("results", [])
    return results[0].get("attributes", {}) if results else {}


# ---------------------------------------------------------------------------
# Step 3: Building regulations (httpx for PDF, cached by BUILDINGUSECODE)
# ---------------------------------------------------------------------------

async def _fetch_building_regulations(
    client: httpx.AsyncClient,
    parcel_id: int,
    building_use_code: int | None,
) -> dict[str, Any]:
    # Check regulation cache by code
    if building_use_code is not None and building_use_code in _reg_cache:
        log.info("Regulation cache HIT for code %s", building_use_code)
        return _reg_cache[building_use_code]

    # Fetch PDF
    url = BUILDING_REPORT_URL.format(pid=parcel_id)
    try:
        resp = await client.get(url, headers=HEADERS, timeout=45)
        if resp.status_code != 200 or len(resp.content) < 500:
            return {"error": f"HTTP {resp.status_code}"}
        regs = _parse_pdf_regulations(resp.content)
    except httpx.TimeoutException:
        return {"error": "PDF download timeout"}
    except Exception as exc:
        return {"error": str(exc)}

    # Cache by building use code
    if building_use_code is not None:
        _reg_cache[building_use_code] = regs
        log.info("Cached regulations for code %s", building_use_code)

    return regs


# ---------------------------------------------------------------------------
# Step 4: SREM market data (httpx)
# ---------------------------------------------------------------------------

async def _fetch_srem_market(client: httpx.AsyncClient) -> dict[str, Any]:
    cache_key = "srem_daily"
    if cache_key in _srem_cache:
        return _srem_cache[cache_key]

    market: dict[str, Any] = {}

    try:
        r = await client.get(f"{SREM_API}/GetMarketIndex", timeout=10)
        d = r.json()
        if d.get("IsSuccess"):
            market["market_index"] = d["Data"]["Index"]
            market["market_index_change"] = d["Data"]["Change"]
    except Exception as exc:
        log.warning("SREM index: %s", exc)

    try:
        r = await client.post(
            f"{SREM_API}/GetTrendingDistricts",
            json={"periodCategory": "D", "citySerial": 0, "areaCategory": "A", "areaSerial": 0},
            timeout=10,
        )
        d = r.json()
        if d.get("IsSuccess"):
            market["trending_districts"] = d["Data"].get("TrendingDistricts", [])
    except Exception as exc:
        log.warning("SREM trending: %s", exc)

    try:
        r = await client.post(
            f"{SREM_API}/GetAreaInfo",
            json={"periodCategory": "D", "period": 1, "areaSerial": 0, "areaType": "A", "cityCode": 0},
            timeout=10,
        )
        d = r.json()
        if d.get("IsSuccess"):
            stats = d["Data"].get("Stats", [])
            if stats:
                market["daily_total_count"] = stats[0].get("TotalCount")
                market["daily_total_price"] = stats[0].get("TotalPrice")
                market["daily_avg_price_sqm"] = stats[0].get("AveragePrice")
                market["daily_total_area"] = stats[0].get("TotalArea")
    except Exception as exc:
        log.warning("SREM area: %s", exc)

    _srem_cache[cache_key] = market
    return market


async def _fetch_srem_district(
    client: httpx.AsyncClient,
    district_name: str,
    city_code: int = 1,  # Riyadh
) -> dict[str, Any]:
    """Fetch SREM market data for a specific district.

    Tries daily first, falls back to weekly then monthly for more data.
    Also fetches Riyadh city-level stats for comparison.
    """
    cache_key = f"srem_district_{district_name}"
    if cache_key in _srem_cache:
        return _srem_cache[cache_key]

    district_data: dict[str, Any] = {"district_name": district_name}

    # Try daily → weekly → monthly for trending districts
    for period, label in [("D", "daily"), ("W", "weekly"), ("M", "monthly")]:
        try:
            r = await client.post(
                f"{SREM_API}/GetTrendingDistricts",
                json={
                    "periodCategory": period,
                    "citySerial": city_code,
                    "areaCategory": "A",
                    "areaSerial": 0,
                },
                timeout=10,
            )
            d = r.json()
            if not d.get("IsSuccess"):
                continue

            districts = d["Data"].get("TrendingDistricts", [])

            # Find our district by name match
            for dist in districts:
                name = dist.get("DistrictName", "")
                if name == district_name or district_name in name or name in district_name:
                    total_area = dist.get("TotalArea", 0)
                    total_price = dist.get("TotalPrice", 0)
                    avg_price = total_price / total_area if total_area > 0 else 0
                    district_data.update({
                        "avg_price_sqm": round(avg_price),
                        "total_deals": dist.get("TotalCount", 0),
                        "total_value": total_price,
                        "total_area": total_area,
                        "district_code": dist.get("DistrictCode"),
                        "period": label,
                        "found": True,
                    })
                    break

            if district_data.get("found"):
                break
        except Exception as exc:
            log.warning("SREM district (%s): %s", label, exc)

    # City-level stats for comparison (Riyadh)
    try:
        r = await client.post(
            f"{SREM_API}/GetAreaInfo",
            json={"periodCategory": "M", "period": 1, "areaSerial": 0, "areaType": "A", "cityCode": city_code},
            timeout=10,
        )
        d = r.json()
        if d.get("IsSuccess"):
            stats = d["Data"].get("Stats", [])
            if stats:
                # Aggregate monthly stats
                total_count = sum(s.get("TotalCount", 0) for s in stats)
                total_price = sum(s.get("TotalPrice", 0) for s in stats)
                total_area_city = sum(s.get("TotalArea", 0) for s in stats)
                min_prices = [s.get("MinPrice", 0) for s in stats if s.get("MinPrice", 0) > 0]
                max_prices = [s.get("MaxPrice", 0) for s in stats if s.get("MaxPrice", 0) > 0]
                district_data["city_total_deals"] = total_count
                district_data["city_avg_price_sqm"] = round(total_price / total_area_city) if total_area_city > 0 else 0
                if min_prices:
                    district_data["city_min_price"] = min(min_prices)
                if max_prices:
                    district_data["city_max_price"] = max(max_prices)
    except Exception as exc:
        log.warning("SREM city stats: %s", exc)

    # Weekly index trend
    try:
        r = await client.get(f"{SREM_API}/GetMarketIndexByDateCategory?dateCategory=W", timeout=10)
        d = r.json()
        if d.get("IsSuccess"):
            index_data = d["Data"].get("marketIndexDtos", [])
            if index_data:
                district_data["index_history"] = [
                    {"date": p.get("CalcDate"), "index": p.get("MarketIndex"), "change": p.get("MarketIndexChange")}
                    for p in index_data[-8:]
                ]
    except Exception as exc:
        log.warning("SREM index history: %s", exc)

    # If district not found in trending, use city avg as fallback
    if not district_data.get("found"):
        district_data["avg_price_sqm"] = district_data.get("city_avg_price_sqm")
        district_data["period"] = "city_average"
        district_data["note"] = f"District '{district_name}' not in current trending. Showing Riyadh city average."

    _srem_cache[cache_key] = district_data
    return district_data


# ---------------------------------------------------------------------------
# Assemble Land Object
# ---------------------------------------------------------------------------

def _build_land_object(
    parcel_id: int,
    query_data: dict,
    identify_data: dict,
    regulations: dict,
    srem_data: dict,
    district_data: dict | None = None,
) -> dict[str, Any]:
    attrs = query_data.get("attributes", {})
    geom = query_data.get("geometry", {})
    rings = geom.get("rings", [])
    clng, clat = _centroid(rings) if rings else (0, 0)

    obj: dict[str, Any] = {
        "parcel_id": parcel_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "parcel_number": attrs.get("PARCELNO"),
        "plan_number": attrs.get("PLANNO"),
        "block_number": attrs.get("BLOCKNO"),
        "object_id": attrs.get("OBJECTID"),
        "district_name": identify_data.get("الحي") or attrs.get("DISTRICT"),
        "municipality": identify_data.get("البلديات الفرعية") or attrs.get("SUBMUNICIPALITY"),
        "centroid": {"lng": clng, "lat": clat},
        "geometry": geom or None,
        "area_sqm": attrs.get("SHAPE.AREA"),
        "building_use_code": attrs.get("BUILDINGUSECODE"),
        "building_code_label": attrs.get("FLGBLDCODE") or identify_data.get("نظام البناء"),
        "primary_use_code": attrs.get("PARCELSUBTYPE"),
        "primary_use_label": identify_data.get("الاستخدام الرئيسي") or LAND_USE_LABELS.get(attrs.get("PARCELSUBTYPE")),
        "secondary_use_code": attrs.get("LANDUSEAGROUP"),
        "detailed_use_code": attrs.get("LANDUSEADETAILED"),
        "detailed_use_label": identify_data.get("استخدام الارض") or LAND_USE_LABELS.get(attrs.get("LANDUSEADETAILED")),
        "reviewed_bld_code": attrs.get("REVIEWED_BLD_CODE"),
        "regulations": {
            "max_floors": regulations.get("max_floors"),
            "far": regulations.get("far"),
            "coverage_ratio": regulations.get("coverage_ratio"),
            "allowed_uses": regulations.get("allowed_uses"),
            "setbacks_raw": regulations.get("setbacks_raw"),
            "setback_values_m": regulations.get("setback_values_m"),
            "notes": regulations.get("notes"),
        },
        "market": {
            "srem_market_index": srem_data.get("market_index"),
            "srem_index_change": srem_data.get("market_index_change"),
            "daily_total_transactions": srem_data.get("daily_total_count"),
            "daily_total_value_sar": srem_data.get("daily_total_price"),
            "daily_avg_price_sqm": srem_data.get("daily_avg_price_sqm"),
            "trending_districts": [
                {"name": d.get("DistrictName"), "city": d.get("CityName"),
                 "deals": d.get("TotalCount"), "total_sar": d.get("TotalPrice")}
                for d in srem_data.get("trending_districts", [])[:5]
            ],
            # District-specific market intelligence
            "district": district_data or {},
        },
    }

    # Health score
    fields = [
        "parcel_number", "plan_number", "district_name", "municipality",
        "area_sqm", "building_code_label", "primary_use_label", "detailed_use_label",
    ]
    reg_fields = ["max_floors", "far", "coverage_ratio", "allowed_uses"]
    mkt_fields = ["srem_market_index", "daily_avg_price_sqm"]
    checked = len(fields) + len(reg_fields) + len(mkt_fields) + 1
    populated = (
        sum(1 for f in fields if obj.get(f))
        + sum(1 for f in reg_fields if obj["regulations"].get(f) not in (None, []))
        + sum(1 for f in mkt_fields if obj["market"].get(f) is not None)
        + (1 if rings else 0)
    )
    obj["data_health"] = {
        "fields_checked": checked,
        "fields_populated": populated,
        "score_pct": round(populated / checked * 100, 1) if checked else 0,
    }

    return obj


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_land_object(
    client: httpx.AsyncClient,
    parcel_id: int,
) -> dict[str, Any]:
    """Fetch a complete Land Object for a parcel ID.

    Uses two-layer caching:
      - Layer 1: full Land Object by parcel_id (1h)
      - Layer 2: decoded regulations by BUILDINGUSECODE (24h)
    """
    # Check land cache
    if parcel_id in _land_cache:
        log.info("Land cache HIT for %d", parcel_id)
        return _land_cache[parcel_id]

    # Step 1: query
    log.info("[%d] Querying parcel...", parcel_id)
    query_data = await _fetch_parcel_query(client, parcel_id)
    attrs = query_data.get("attributes", {})
    geom = query_data.get("geometry", {})
    rings = geom.get("rings", [])

    # Step 2: identify
    identify_data: dict = {}
    if rings:
        lng, lat = _centroid(rings)
        log.info("[%d] Identifying at (%.5f, %.5f)...", parcel_id, lng, lat)
        identify_data = await _fetch_parcel_identify(client, lng, lat)

    # Step 3: regulations (cached by BUILDINGUSECODE)
    bld_code = attrs.get("BUILDINGUSECODE")
    log.info("[%d] Fetching regulations (code=%s)...", parcel_id, bld_code)
    regulations = await _fetch_building_regulations(client, parcel_id, bld_code)

    # Step 4: SREM market data (national + district)
    log.info("[%d] Fetching SREM market data...", parcel_id)
    srem_data = await _fetch_srem_market(client)

    # Step 5: District-specific market intelligence
    district_name = identify_data.get("الحي") or ""
    district_data: dict = {}
    if district_name:
        log.info("[%d] Fetching SREM district data for '%s'...", parcel_id, district_name)
        district_data = await _fetch_srem_district(client, district_name)

    # Assemble
    land_obj = _build_land_object(parcel_id, query_data, identify_data, regulations, srem_data, district_data)

    # Cache land object
    _land_cache[parcel_id] = land_obj
    return land_obj
