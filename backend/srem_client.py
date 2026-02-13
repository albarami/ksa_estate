"""SREM (Saudi Real Estate Market) API client.

Fetches national market data and district-specific market intelligence.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from cachetools import TTLCache

log = logging.getLogger("srem_client")

SREM_API = "https://prod-srem-api-srem.moj.gov.sa/api/v1/Dashboard"

_srem_cache: TTLCache = TTLCache(maxsize=50, ttl=300)  # 5 min


async def fetch_market(client: httpx.AsyncClient) -> dict[str, Any]:
    """Fetch national SREM market snapshot (index, trending, area stats)."""
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


async def fetch_district(
    client: httpx.AsyncClient,
    district_name: str,
    city_code: int = 1,
) -> dict[str, Any]:
    """Fetch SREM market data for a specific district.

    Tries daily -> weekly -> monthly for trending districts.
    Falls back to Riyadh city average when district is not trending.
    """
    cache_key = f"srem_district_{district_name}"
    if cache_key in _srem_cache:
        return _srem_cache[cache_key]

    data: dict[str, Any] = {"district_name": district_name}

    # Try daily -> weekly -> monthly
    for period, label in [("D", "daily"), ("W", "weekly"), ("M", "monthly")]:
        try:
            r = await client.post(
                f"{SREM_API}/GetTrendingDistricts",
                json={"periodCategory": period, "citySerial": city_code, "areaCategory": "A", "areaSerial": 0},
                timeout=10,
            )
            d = r.json()
            if not d.get("IsSuccess"):
                continue
            for dist in d["Data"].get("TrendingDistricts", []):
                name = dist.get("DistrictName", "")
                if name == district_name or district_name in name or name in district_name:
                    total_area = dist.get("TotalArea", 0)
                    total_price = dist.get("TotalPrice", 0)
                    data.update({
                        "avg_price_sqm": round(total_price / total_area) if total_area > 0 else 0,
                        "total_deals": dist.get("TotalCount", 0),
                        "total_value": total_price,
                        "total_area": total_area,
                        "district_code": dist.get("DistrictCode"),
                        "period": label,
                        "found": True,
                    })
                    break
            if data.get("found"):
                break
        except Exception as exc:
            log.warning("SREM district (%s): %s", label, exc)

    # City-level stats for comparison
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
                total_price = sum(s.get("TotalPrice", 0) for s in stats)
                total_area_city = sum(s.get("TotalArea", 0) for s in stats)
                data["city_total_deals"] = sum(s.get("TotalCount", 0) for s in stats)
                data["city_avg_price_sqm"] = round(total_price / total_area_city) if total_area_city > 0 else 0
    except Exception as exc:
        log.warning("SREM city stats: %s", exc)

    # Weekly index trend
    try:
        r = await client.get(f"{SREM_API}/GetMarketIndexByDateCategory?dateCategory=W", timeout=10)
        d = r.json()
        if d.get("IsSuccess"):
            pts = d["Data"].get("marketIndexDtos", [])
            if pts:
                data["index_history"] = [
                    {"date": p.get("CalcDate"), "index": p.get("MarketIndex"), "change": p.get("MarketIndexChange")}
                    for p in pts[-8:]
                ]
    except Exception as exc:
        log.warning("SREM index history: %s", exc)

    # Fallback when district not in trending
    if not data.get("found"):
        data["avg_price_sqm"] = data.get("city_avg_price_sqm")
        data["period"] = "city_average"
        data["note"] = f"District '{district_name}' not in current trending. Showing Riyadh city average."

    _srem_cache[cache_key] = data
    return data


def clear_cache() -> None:
    """Clear SREM caches."""
    _srem_cache.clear()
