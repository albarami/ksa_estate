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

from backend.srem_client import fetch_market as _fetch_srem_market
from backend.srem_client import fetch_district as _fetch_srem_district
from backend.srem_client import clear_cache as _clear_srem_cache

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
REFERER = "https://mapservice.alriyadh.gov.sa/geoportal/geomap"
HEADERS = {"Referer": REFERER}

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------

_land_cache: TTLCache = TTLCache(maxsize=500, ttl=3600)       # 1 hour
_reg_cache: TTLCache = TTLCache(maxsize=200, ttl=86400)       # 24 hours


def clear_caches() -> None:
    """Clear all caches (for testing)."""
    _land_cache.clear()
    _reg_cache.clear()
    _clear_srem_cache()


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

def _normalize_arabic(text: str) -> str:
    """Normalize Arabic Presentation Forms to standard Unicode.

    PDFs often use U+FB50-FDFF and U+FE70-FEFF ligature/presentation forms.
    This converts them to standard Arabic letters for reliable matching.
    """
    import unicodedata
    # NFKC normalization decomposes most presentation forms
    normalized = unicodedata.normalize("NFKC", text)
    return normalized


def _parse_pdf_regulations(pdf_bytes: bytes) -> dict[str, Any]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    raw_text = "".join(page.get_text("text") for page in doc)
    doc.close()

    # Normalize Arabic presentation forms to standard Unicode
    text = _normalize_arabic(raw_text)

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

    # Allowed uses (text is NFKC-normalized — standard Arabic only)
    use_map = {
        "\u0633\u0643\u0646\u064a": "residential",
        "\u062a\u062c\u0627\u0631\u064a": "commercial",
        "\u0645\u0643\u0627\u062a\u0628": "offices",
        "\u0645\u062e\u062a\u0644\u0637": "mixed_use",
    }
    uses: list[str] = []
    in_uses = False
    for line in lines:
        if "\u0627\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645\u0627\u062a" in line:
            in_uses = True
            continue
        if in_uses:
            if "\u0627\u0644\u0627\u0631\u062a\u062f\u0627\u062f" in line:
                break
            for ar, en in use_map.items():
                if ar in line and en not in uses:
                    uses.append(en)
    regs["allowed_uses"] = uses

    # Floors — parse the heights section (text is NFKC-normalized now)
    floor_count = None
    in_heights = False
    height_lines: list[str] = []
    for line in lines:
        if "\u0627\u0644\u0627\u0631\u062a\u0641\u0627\u0639" in line:
            in_heights = True
            continue
        if in_heights:
            if "\u0645\u0639\u0627\u0645\u0644" in line or "\u0646\u0633\u0628\u0629" in line or "\u0645\u0648\u0627\u0642\u0641" in line:
                break
            height_lines.append(line)
    height_text = " ".join(height_lines).strip()

    # Count floor indicators (standard Arabic after NFKC normalization)
    floor_words = [
        "\u0623\u0631\u0636\u064a",  # أرضي (ground)
        "\u0623\u0648\u0644",        # أول (first)
        "\u062b\u0627\u0646\u064a",  # ثاني (second)
        "\u062b\u0627\u0644\u062b",  # ثالث (third)
        "\u0631\u0627\u0628\u0639",  # رابع (fourth)
        "\u062e\u0627\u0645\u0633",  # خامس (fifth)
    ]
    if height_text:
        count = sum(1 for w in floor_words if w in height_text)
        if count > 0:
            floor_count = count

    # Fallback patterns in full text
    if not floor_count:
        if "\u062f\u0648\u0631\u064a\u0646" in cleaned:
            floor_count = 2
        elif "\u062b\u0644\u0627\u062b" in cleaned and "\u0623\u062f\u0648\u0627\u0631" in cleaned:
            floor_count = 3
        elif "\u0623\u0631\u0628\u0639" in cleaned and "\u0623\u062f\u0648\u0627\u0631" in cleaned:
            floor_count = 4
        elif "\u062e\u0645\u0633" in cleaned and "\u0623\u062f\u0648\u0627\u0631" in cleaned:
            floor_count = 5

    # Fallback: numeric "N أدوار"
    if not floor_count:
        nm = re.search(r"(\d+)\s*\u0623\u062f\u0648\u0627\u0631", cleaned)
        if nm:
            floor_count = int(nm.group(1))

    if floor_count:
        regs["max_floors"] = floor_count

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

    # Setbacks (NFKC-normalized)
    in_sb = False
    sb_lines: list[str] = []
    for line in lines:
        if "\u0627\u0644\u0627\u0631\u062a\u062f\u0627\u062f" in line:
            in_sb = True
            rest = re.sub(r"\u0627\u0644\u0627\u0631\u062a\u062f\u0627\u062f\u0627\u062a?", "", line).strip()
            if rest:
                sb_lines.append(rest)
            continue
        if in_sb:
            if "\u0627\u0644\u0627\u0631\u062a\u0641\u0627\u0639" in line:
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

def _parse_plan_attrs(attrs: dict) -> dict[str, Any]:
    """Extract plan info from layer 3 attributes."""
    return {
        "plan_date_hijri": attrs.get("\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0645\u062e\u0637\u0637 \u0627\u0644\u0647\u062c\u0631\u064a"),
        "plan_year": attrs.get("\u0633\u0646\u0629 \u0627\u0644\u0645\u062e\u0637\u0637"),
        "plan_status": attrs.get("PLANSTATUS"),
        "plan_use": attrs.get("PLANUSE"),
        "plan_type": attrs.get("PLANTYPENAME"),
    }


def _parse_district_attrs(attrs: dict) -> dict[str, Any]:
    """Extract district demographics from layer 4 attributes."""
    pop = attrs.get("\u0625\u062c\u0645\u0627\u0644\u064a \u0633\u0643\u0627\u0646 \u0627\u0644\u062d\u064a") or attrs.get("CURRENTPOPULATION")
    area_m2 = attrs.get("\u0627\u0644\u0645\u0633\u0627\u062d\u0629 \u0627\u0644\u062d\u0642\u064a\u0642\u0629 -  \u06452") or attrs.get("\u0627\u0644\u0645\u0633\u0627\u062d\u0629")
    return {
        "population": pop,
        "population_density": attrs.get("\u0627\u0644\u0643\u062b\u0627\u0641\u0629 \u0627\u0644\u0633\u0643\u0627\u0646\u064a\u0629"),
        "area_m2": area_m2,
        "district_name_ar": attrs.get("\u0627\u0633\u0645 \u0627\u0644\u062d\u064a"),
        "district_name_en": attrs.get("District Name"),
        "district_code": attrs.get("\u0631\u0642\u0645 \u0627\u0644\u062d\u064a"),
    }


def _identify_url(lng: float, lat: float, extent: float, layers: str) -> str:
    """Build an ArcGIS identify URL."""
    return (
        f"{PROXY}?{PARCELS_SERVER}/identify"
        f"?geometry={lng},{lat}"
        f"&geometryType=esriGeometryPoint&sr=4326&tolerance=10"
        f"&mapExtent={lng-extent},{lat-extent},{lng+extent},{lat+extent}"
        f"&imageDisplay=1440,900,96&layers={layers}"
        f"&returnGeometry=false&f=json"
    )


async def _fetch_parcel_identify(
    client: httpx.AsyncClient, lng: float, lat: float,
) -> dict[str, Any]:
    """Identify all layers at a point. Returns merged attrs with _plan_info, _district_info."""
    resp = await client.get(_identify_url(lng, lat, 0.002, "all"), headers=HEADERS, timeout=15)
    results = json.loads(resp.text).get("results", [])

    merged: dict[str, Any] = {}
    plan_info: dict[str, Any] = {}
    district_info: dict[str, Any] = {}

    for result in results:
        lid = result.get("layerId")
        attrs = result.get("attributes", {})
        if lid == 2:
            merged.update(attrs)
        elif lid == 3:
            plan_info = _parse_plan_attrs(attrs)
        elif lid == 4:
            district_info = _parse_district_attrs(attrs)
        elif lid == 2222 and not merged:
            merged.update(attrs)

    # Layer 3 is scale-dependent — retry with wider extent
    if not plan_info:
        try:
            resp2 = await client.get(_identify_url(lng, lat, 0.05, "all:3"), headers=HEADERS, timeout=15)
            for r in json.loads(resp2.text).get("results", []):
                if r.get("layerId") == 3:
                    plan_info = _parse_plan_attrs(r.get("attributes", {}))
                    break
        except Exception as exc:
            log.warning("Wide identify for layer 3: %s", exc)

    # Layer 4 needs even wider extent
    if not district_info:
        try:
            resp3 = await client.get(_identify_url(lng, lat, 0.1, "all:4"), headers=HEADERS, timeout=15)
            for r in json.loads(resp3.text).get("results", []):
                if r.get("layerId") == 4:
                    district_info = _parse_district_attrs(r.get("attributes", {}))
                    break
        except Exception as exc:
            log.warning("Wide identify for layer 4: %s", exc)

    merged["_plan_info"] = plan_info
    merged["_district_info"] = district_info
    return merged


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
# Step 4: SREM market data — imported from srem_client.py
# ---------------------------------------------------------------------------


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
    # Source 1: Query layer 2 (PARCELID exact match)
    attrs = query_data.get("attributes", {})
    geom = query_data.get("geometry", {})
    rings = geom.get("rings", [])
    clng, clat = _centroid(rings) if rings else (0, 0)

    # Source 2: Identify layers (2222, 2, 3, 4) — point-based spatial match
    # Layer 2222 fields use Arabic names; these serve as fallbacks
    ident = identify_data  # merged attrs from all identify layers

    obj: dict[str, Any] = {
        "parcel_id": parcel_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        # Cross-sourced: Query → Identify fallback
        "parcel_number": attrs.get("PARCELNO") or ident.get("رقم القطعة"),
        "plan_number": attrs.get("PLANNO") or ident.get("رقم المخطط"),
        "block_number": attrs.get("BLOCKNO") or ident.get("رقم البلوك"),
        "object_id": attrs.get("OBJECTID"),
        "district_name": ident.get("الحي") or attrs.get("DISTRICT"),
        "municipality": ident.get("البلديات الفرعية") or attrs.get("SUBMUNICIPALITY") or ident.get("البلدية"),
        "centroid": {"lng": clng, "lat": clat},
        "geometry": geom or None,
        # Area: Query is authoritative, identify layer as fallback
        "area_sqm": attrs.get("SHAPE.AREA") or ident.get("المساحة"),
        "building_use_code": attrs.get("BUILDINGUSECODE"),
        # Building code: Query → Identify fallback
        "building_code_label": attrs.get("FLGBLDCODE") or ident.get("نظام البناء") or ident.get("اشترطات نظام البناء"),
        "primary_use_code": attrs.get("PARCELSUBTYPE"),
        "primary_use_label": ident.get("الاستخدام الرئيسي") or LAND_USE_LABELS.get(attrs.get("PARCELSUBTYPE")),
        "secondary_use_code": attrs.get("LANDUSEAGROUP"),
        "detailed_use_code": attrs.get("LANDUSEADETAILED"),
        "detailed_use_label": ident.get("استخدام الارض") or LAND_USE_LABELS.get(attrs.get("LANDUSEADETAILED")),
        "reviewed_bld_code": attrs.get("REVIEWED_BLD_CODE"),
        # Track which sources populated data (for transparency)
        "data_sources": {
            "query_layer_2": bool(attrs),
            "identify_layer_2222": bool(ident.get("رمز القطعة")),
            "identify_layer_3_plan": bool(ident.get("_plan_info")),
            "identify_layer_4_district": bool(ident.get("_district_info")),
            "building_pdf": not regulations.get("error"),
            "srem_national": bool(srem_data.get("market_index")),
            "srem_district": bool(district_data),
        },
        # Plan info (from Geoportal layer 3)
        "plan_info": identify_data.get("_plan_info", {}),
        # District demographics (from Geoportal layer 4)
        "district_demographics": identify_data.get("_district_info", {}),
        "regulations": {
            "max_floors": regulations.get("max_floors"),
            "far": regulations.get("far"),
            "coverage_ratio": regulations.get("coverage_ratio"),
            "allowed_uses": regulations.get("allowed_uses"),
            "setbacks_raw": regulations.get("setbacks_raw"),
            "setback_values_m": regulations.get("setback_values_m"),
            "notes": regulations.get("notes"),
            "source": "building_pdf" if not regulations.get("error") else "unavailable",
            "pdf_error": regulations.get("error"),
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
