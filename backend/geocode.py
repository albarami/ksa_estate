"""Parse Google Maps URLs/coordinates and find the parcel at that location.

Supports:
  - Google Maps URLs (short and long)
  - Raw coordinates: "24.648843, 46.658778"
  - Decimal degrees: "24.648843 46.658778"
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

log = logging.getLogger("geocode")

PROXY = (
    "https://mapservice.alriyadh.gov.sa"
    "/APIGEOPORTALN/Handler/proxy.ashx"
)
PARCELS_SERVER = (
    "https://maps.alriyadh.gov.sa/gprtl/rest/services"
    "/WebMercator/WMParcelsLayerOne/MapServer"
)
REFERER = "https://mapservice.alriyadh.gov.sa/geoportal/geomap"


def parse_coordinates(text: str) -> tuple[float, float] | None:
    """Extract lat/lng from a Google Maps URL or coordinate string.

    Returns:
        (latitude, longitude) or None if parsing fails.
    """
    text = text.strip()

    # Pattern 1 (PRIORITY): Google Maps !3d (lat) and !4d (lng) — the actual pin
    lat_m = re.search(r'!3d(-?\d+\.?\d*)', text)
    lng_m = re.search(r'!4d(-?\d+\.?\d*)', text)
    if lat_m and lng_m:
        return float(lat_m.group(1)), float(lng_m.group(1))

    # Pattern 2: @lat,lng — map viewport center (fallback, less precise)
    m = re.search(r'@(-?\d+\.?\d*),(-?\d+\.?\d*)', text)
    if m:
        return float(m.group(1)), float(m.group(2))

    # Pattern 3: URL with place/ followed by coordinates in DMS or decimal
    m = re.search(r'place/(-?\d+\.?\d*)[°%C2%B0]?\s*[NS]?\s*[,+\s]\s*(-?\d+\.?\d*)', text)
    if m:
        return float(m.group(1)), float(m.group(2))

    # Pattern 4: Raw "lat, lng" or "lat lng"
    m = re.match(r'^\s*(-?\d+\.?\d*)\s*[,\s]\s*(-?\d+\.?\d*)\s*$', text)
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))
        # Sanity check: Riyadh is roughly lat 24-25, lng 46-47
        if 20 < lat < 30 and 40 < lng < 50:
            return lat, lng
        # Maybe they swapped? Try lng, lat
        if 20 < lng < 30 and 40 < lat < 50:
            return lng, lat

    return None


async def find_parcel_at_coords(
    client: httpx.AsyncClient,
    lat: float,
    lng: float,
) -> dict[str, Any] | None:
    """Hit the MapServer identify to find the parcel containing a point.

    Returns:
        Parcel attributes dict or None if no parcel found.
    """
    url = (
        f"{PROXY}?{PARCELS_SERVER}/identify"
        f"?geometry={lng},{lat}"
        f"&geometryType=esriGeometryPoint&sr=4326&tolerance=10"
        f"&mapExtent={lng-0.004},{lat-0.003},{lng+0.004},{lat+0.003}"
        f"&imageDisplay=1440,900,96&layers=all:2"
        f"&returnGeometry=false&f=json"
    )

    resp = await client.get(url, headers={"Referer": REFERER}, timeout=15)
    data = resp.json()
    results = data.get("results", [])

    if not results:
        return None

    attrs = results[0].get("attributes", {})
    # Extract parcel ID from various possible field names
    parcel_id = (
        attrs.get("PARCELID")
        or attrs.get("رمز قطعة الأرض")
        or attrs.get("رمز القطعة")
    )

    if parcel_id:
        try:
            parcel_id = int(parcel_id)
        except (ValueError, TypeError):
            pass

    return {
        "parcel_id": parcel_id,
        "parcel_number": attrs.get("PARCELNO") or attrs.get("رقم القطعة"),
        "plan_number": attrs.get("PLANNO") or attrs.get("رقم المخطط"),
        "district": attrs.get("الحي"),
        "municipality": attrs.get("البلديات الفرعية"),
        "building_code": attrs.get("FLGBLDCODE") or attrs.get("نظام البناء"),
        "area_sqm": attrs.get("SHAPE.AREA") or attrs.get("مساحة القطعة"),
        "land_use": attrs.get("استخدام الارض"),
        "coordinates": {"lat": lat, "lng": lng},
        "all_attributes": attrs,
    }
