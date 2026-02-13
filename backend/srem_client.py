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
    city_name: str = "\u0627\u0644\u0631\u064a\u0627\u0636",
) -> dict[str, Any]:
    """Fetch SREM market data for a specific district.

    Tries daily -> weekly -> monthly for trending districts.
    Also collects Riyadh-specific districts for price comparison.
    citySerial is ignored by the API, so we filter client-side by CityName.
    """
    cache_key = f"srem_district_{district_name}"
    if cache_key in _srem_cache:
        return _srem_cache[cache_key]

    data: dict[str, Any] = {"district_name": district_name}

    # Collect all Riyadh districts across periods for a city-level avg
    riyadh_districts: list[dict] = []

    # Try daily -> weekly -> monthly
    for period, label in [("D", "daily"), ("W", "weekly"), ("M", "monthly")]:
        try:
            r = await client.post(
                f"{SREM_API}/GetTrendingDistricts",
                json={"periodCategory": period, "citySerial": 0, "areaCategory": "A", "areaSerial": 0},
                timeout=10,
            )
            d = r.json()
            if not d.get("IsSuccess"):
                continue

            for dist in d["Data"].get("TrendingDistricts", []):
                dist_city = dist.get("CityName", "")
                name = dist.get("DistrictName", "")

                # Collect Riyadh districts for city average
                if city_name in dist_city or dist_city in city_name:
                    riyadh_districts.append(dist)

                # Exact district match
                if not data.get("found") and (name == district_name or district_name in name or name in district_name):
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
        except Exception as exc:
            log.warning("SREM district (%s): %s", label, exc)

    # Compute Riyadh average from actual trending districts (not the useless GetAreaInfo)
    if riyadh_districts:
        total_price_ry = sum(d.get("TotalPrice", 0) for d in riyadh_districts)
        total_area_ry = sum(d.get("TotalArea", 0) for d in riyadh_districts)
        data["city_avg_price_sqm"] = round(total_price_ry / total_area_ry) if total_area_ry > 0 else None
        data["city_total_deals"] = sum(d.get("TotalCount", 0) for d in riyadh_districts)
        data["city_districts_sampled"] = len(riyadh_districts)
    else:
        data["city_avg_price_sqm"] = None

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

    # When district not found, use Riyadh average OR set null (don't use 144)
    if not data.get("found"):
        city_avg = data.get("city_avg_price_sqm")
        if city_avg and city_avg > 500:
            # Use Riyadh-specific avg from actual transactions
            data["avg_price_sqm"] = city_avg
            data["period"] = "riyadh_average"
            data["note"] = f"District '{district_name}' not in trending. Using Riyadh transaction average."
        else:
            # No reliable price data — don't guess
            data["avg_price_sqm"] = None
            data["period"] = "unavailable"
            data["note"] = f"No SREM price data available for '{district_name}'."

    _srem_cache[cache_key] = data
    return data


def clear_cache() -> None:
    """Clear SREM caches."""
    _srem_cache.clear()
