"""Test SREM district-level data fetch."""
import httpx
import asyncio
from backend.data_fetch_http import _fetch_srem_district

async def test():
    async with httpx.AsyncClient(verify=False) as c:
        for name in ["\u0627\u0644\u0645\u0644\u0642\u0627", "\u0627\u0644\u0639\u0627\u0631\u0636", "\u0627\u0644\u0631\u0641\u064a\u0639\u0629"]:
            d = await _fetch_srem_district(c, name)
            found = d.get("found", False)
            avg = d.get("avg_price_sqm", "N/A")
            deals = d.get("total_deals", 0)
            period = d.get("period", "?")
            city_avg = d.get("city_avg_price_sqm", "N/A")
            idx = d.get("index_history", [])
            print(f"{name}: found={found}, avg={avg} SAR/m2, deals={deals} ({period}), city_avg={city_avg}")
            if idx:
                latest = idx[-1]
                print(f"  Index: {latest['index']:,.0f} (change: {latest['change']})")
            print()

asyncio.run(test())
