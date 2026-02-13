"""Test that district market data flows through the parcel API."""
import httpx
import json

r = httpx.post("http://127.0.0.1:8000/api/parcel/3710897", timeout=30)
land = r.json()

print(f"District: {land.get('district_name')}")
print(f"\nMarket data:")
market = land.get("market", {})
district = market.get("district", {})
print(f"  District name: {district.get('district_name')}")
print(f"  Avg price/m2: {district.get('avg_price_sqm')}")
print(f"  Period: {district.get('period')}")
print(f"  City avg: {district.get('city_avg_price_sqm')}")
print(f"  Note: {district.get('note', 'none')}")
print(f"  Index history: {len(district.get('index_history', []))} points")

if district.get("index_history"):
    for p in district["index_history"][-3:]:
        print(f"    {p['date']}: {p['index']:,.0f} ({p['change']:+.2f})")
