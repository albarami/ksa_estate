"""Check the park parcel from the user's link."""
import httpx
from backend.geocode import parse_coordinates, find_parcel_at_coords
import asyncio

URL = "https://www.google.com/maps/place/24%C2%B038'52.8%22N+46%C2%B039'26.5%22E/@24.6479909,46.6547981,17z/data=!3m1!4b1!4m4!3m3!8m2!3d24.647986!4d46.657373"

coords = parse_coordinates(URL)
print(f"Parsed coordinates: {coords}")

# The URL has @24.6479909,46.6547981 and !3d24.647986!4d46.657373
# The !3d/!4d are the actual pin location
lat, lng = 24.647986, 46.657373
print(f"Pin location: lat={lat}, lng={lng}")

async def main():
    async with httpx.AsyncClient(verify=False) as client:
        result = await find_parcel_at_coords(client, lat, lng)
        if result:
            print(f"\nParcel found:")
            for k, v in result.items():
                if k != "all_attributes":
                    print(f"  {k}: {v}")
            print(f"\nAll attributes:")
            for k, v in result.get("all_attributes", {}).items():
                print(f"  {k}: {v}")
        else:
            print("No parcel found")

        # Also check the original Al-Hada main point
        print(f"\n--- Main Al-Hada point (24.648843, 46.658778) ---")
        r2 = await find_parcel_at_coords(client, 24.648843, 46.658778)
        if r2:
            print(f"  ParcelID: {r2['parcel_id']}")
            print(f"  Area: {r2['area_sqm']}")
            print(f"  Code: {r2['building_code']}")

        # Check if they're different parcels
        if result and r2:
            p1 = result["parcel_id"]
            p2 = r2["parcel_id"]
            print(f"\nPark parcel: {p1}")
            print(f"Main parcel: {p2}")
            print(f"Same parcel? {p1 == p2}")
            if p1 != p2:
                a1 = float(result.get("area_sqm") or 0)
                a2 = float(r2.get("area_sqm") or 0)
                print(f"Combined area: {a1 + a2:,.0f} m2")

asyncio.run(main())
