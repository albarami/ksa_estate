"""Test the FastAPI backend endpoints."""

import time
import httpx

BASE = "http://127.0.0.1:8000"

def main():
    # Health
    print("=== Health ===")
    r = httpx.get(f"{BASE}/health")
    print(r.json())

    # Parcel (first call)
    print("\n=== Parcel 3710897 ===")
    t0 = time.time()
    r = httpx.post(f"{BASE}/api/parcel/3710897", timeout=30)
    elapsed = time.time() - t0
    data = r.json()
    district = data.get("district_name", "?")
    code = data.get("building_code_label", "?")
    health = data.get("data_health", {}).get("score_pct", 0)
    print(f"  Status: {r.status_code}, Time: {elapsed:.1f}s")
    print(f"  District: {district}")
    print(f"  Code: {code}")
    print(f"  Health: {health}%")

    # Parcel (cached)
    print("\n=== Parcel 3710897 (cached) ===")
    t0 = time.time()
    r = httpx.post(f"{BASE}/api/parcel/3710897", timeout=30)
    elapsed = time.time() - t0
    print(f"  Status: {r.status_code}, Time: {elapsed:.1f}s (should be <0.1s)")

    # Proforma
    print("\n=== Proforma ===")
    t0 = time.time()
    r = httpx.post(f"{BASE}/api/proforma", json={
        "parcel_id": 3710897,
        "overrides": {"land_price_per_sqm": 5000, "sale_price_per_sqm": 8000},
    }, timeout=30)
    elapsed = time.time() - t0
    pf = r.json().get("proforma", {})
    fs = pf.get("fund_size", {}).get("total_fund_size", 0)
    irr = pf.get("kpis", {}).get("irr")
    conf = pf.get("data_health", {}).get("confidence_pct", 0)
    print(f"  Status: {r.status_code}, Time: {elapsed:.1f}s")
    print(f"  Fund size: {fs:,.0f} SAR")
    if irr is not None:
        print(f"  IRR: {irr:.2%}")
    print(f"  Confidence: {conf}%")

    # Scenarios
    print("\n=== Scenarios ===")
    r = httpx.post(f"{BASE}/api/proforma/scenario", json={
        "parcel_id": 3710897,
        "base_overrides": {"land_price_per_sqm": 5000},
        "scenarios": [
            {"name": "Conservative", "overrides": {"sale_price_per_sqm": 7000}},
            {"name": "Base", "overrides": {"sale_price_per_sqm": 9000}},
            {"name": "Aggressive", "overrides": {"sale_price_per_sqm": 12000}},
        ],
    }, timeout=30)
    scenarios = r.json().get("scenarios", [])
    for s in scenarios:
        s_irr = s["proforma"]["kpis"].get("irr")
        s_profit = s["proforma"]["kpis"].get("equity_net_profit", 0)
        irr_str = f"{s_irr:.1%}" if s_irr is not None else "N/A"
        print(f"  {s['name']}: IRR={irr_str}, Profit={s_profit:,.0f} SAR")

    # Excel
    print("\n=== Excel download ===")
    r = httpx.get(
        f"{BASE}/api/excel/3710897",
        params={"land_price_per_sqm": 5000, "sale_price_per_sqm": 8000},
        timeout=30,
    )
    print(f"  Status: {r.status_code}, Size: {len(r.content):,} bytes")
    if r.status_code == 200:
        with open("test_proforma.xlsx", "wb") as f:
            f.write(r.content)
        print("  Saved: test_proforma.xlsx")

    print("\nAll tests complete.")


if __name__ == "__main__":
    main()
