"""Test the /api/locate endpoint with various inputs."""
import httpx

BASE = "http://127.0.0.1:8000"

tests = [
    ("Parcel ID", "3834663"),
    ("Google Maps URL", "https://www.google.com/maps/place/24%C2%B038'55.8%22N+46%C2%B039'31.6%22E/@24.648843,46.658778,17z"),
    ("Coordinates", "24.648843, 46.658778"),
    ("Short coords", "24.8256 46.6526"),
]

for name, query in tests:
    print(f"\n=== {name}: {query[:60]}... ===")
    try:
        r = httpx.post(f"{BASE}/api/locate", json={"query": query}, timeout=30)
        if r.status_code == 200:
            d = r.json()
            pid = d.get("parcel_id")
            src = d.get("source")
            lo = d.get("land_object", {})
            district = lo.get("district_name", "?")
            code = lo.get("building_code_label", "?")
            area = lo.get("area_sqm", 0)
            print(f"  OK: parcel={pid}, source={src}, district={district}, code={code}, area={area:,.0f}")
        else:
            print(f"  ERROR {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  FAILED: {e}")
