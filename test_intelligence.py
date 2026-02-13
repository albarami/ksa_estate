"""Test computed intelligence metrics."""
from computation_engine import compute_proforma

# Al-Hada (big parcel, cash deal)
land_h = {"area_sqm": 35000, "regulations": {"max_floors": None, "far": 1.5, "coverage_ratio": 0.6, "allowed_uses": ["residential"]},
           "building_code_label": "test", "district_name": "test", "municipality": "test", "parcel_id": 0, "parcel_number": "0", "plan_number": "0",
           "market": {"srem_market_index": 10712, "trending_districts": []}}
ov_h = {"land_price_per_sqm": 7000, "sale_price_per_sqm": 12500, "infrastructure_cost_per_sqm": 500, "superstructure_cost_per_sqm": 2500,
        "parking_area_sqm": 15000, "parking_cost_per_sqm": 2000, "fund_period_years": 3, "bank_ltv_pct": 0.667, "interest_rate_pct": 0.08, "efficiency_ratio": 1.0}

# Al-Malqa (small parcel, in-kind deal)
land_m = {"area_sqm": 3712, "regulations": {"max_floors": 2, "far": 1.625, "coverage_ratio": 0.65, "allowed_uses": ["residential"]},
           "building_code_label": "test", "district_name": "test", "municipality": "test", "parcel_id": 0, "parcel_number": "0", "plan_number": "0",
           "market": {"srem_market_index": 10712, "trending_districts": []}}
ov_m = {"land_price_per_sqm": 13000, "sale_price_per_sqm": 15500, "infrastructure_cost_per_sqm": 300, "superstructure_cost_per_sqm": 2500,
        "parking_area_sqm": 0, "far": 1.625, "in_kind_pct": 0.70, "fund_period_years": 3, "bank_ltv_pct": 0.667, "interest_rate_pct": 0.08,
        "efficiency_ratio": 1.0, "other_indirect_pct": 0.05}

for name, land, ov in [("Al-Hada (35K m2, cash)", land_h, ov_h), ("Al-Malqa (3.7K m2, 70% in-kind)", land_m, ov_m)]:
    r = compute_proforma(land, ov)
    k = r["kpis"]
    print(f"\n{'='*50}")
    print(f"{name}")
    print(f"{'='*50}")
    print(f"  IRR:                {k['irr']:.2%}" if k["irr"] else "  IRR: N/A")
    print(f"  Deal Score:         {k['deal_score']}/100")
    print(f"  Break-even price:   {k['break_even_price_sqm']:,.0f} SAR/m2")
    print(f"  Land cost/GBA:      {k['land_cost_per_gba']:,.0f} SAR/m2")
    print(f"  Revenue multiple:   {k['revenue_multiple']:.2f}x")
    print(f"  Fund overhead:      {k['fund_overhead_ratio']:.1%}")
    print(f"  Risk flags:         {k['risk_flags']}")
