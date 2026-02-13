"""Check the Al-Aarid parcel."""
import httpx
import asyncio
from backend.geocode import find_parcel_at_coords

async def main():
    async with httpx.AsyncClient(verify=False) as client:
        lat, lng = 24.9240833, 46.5701111
        result = await find_parcel_at_coords(client, lat, lng)
        if result:
            print("Parcel found:")
            for k, v in result.items():
                if k != "all_attributes":
                    print(f"  {k}: {v}")

            # Compare with user's data
            area = float(result.get("area_sqm") or 0)
            print(f"\n=== COMPARISON ===")
            print(f"  User says:    88,567.67 m2")
            print(f"  Geoportal:    {area:,.2f} m2")
            print(f"  Match: {'YES' if abs(area - 88567.67) / 88567.67 < 0.05 else 'CHECK'}")
            print(f"  District:     {result.get('district')} (user says: العارض)")
            print(f"  Plan:         {result.get('plan_number')} (user says: 3471)")
            print(f"  Code:         {result.get('building_code')}")
        else:
            print("No parcel found at these coordinates")

asyncio.run(main())
