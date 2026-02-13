"""Validate computation engine against Al-Malqa deal."""
from computation_engine import compute_proforma

land = {
    "area_sqm": 3712,
    "regulations": {"max_floors": 2, "far": 1.625, "coverage_ratio": 0.65, "allowed_uses": ["residential"]},
    "building_code_label": "test", "district_name": "الملقا",
    "municipality": "test", "parcel_id": 0, "parcel_number": "0", "plan_number": "0",
    "market": {"srem_market_index": 10712, "trending_districts": []},
}

overrides = {
    "land_price_per_sqm": 13000,
    "sale_price_per_sqm": 15500,
    "infrastructure_cost_per_sqm": 300,
    "superstructure_cost_per_sqm": 2500,
    "parking_area_sqm": 0,
    "far": 1.625,
    "in_kind_pct": 0.70,
    "fund_period_years": 3,
    "bank_ltv_pct": 0.667,
    "interest_rate_pct": 0.08,
    "efficiency_ratio": 1.0,
    "other_indirect_pct": 0.05,
}

r = compute_proforma(land, overrides)

ref = {
    "Fund Size": (79_304_975, r["fund_size"]["total_fund_size"]),
    "Equity (cash)": (13_355_108, r["fund_size"]["equity_amount"]),
    "In-Kind": (33_779_200, r["fund_size"]["in_kind_contribution"]),
    "Bank Loan": (32_170_667, r["fund_size"]["bank_loan"]),
    "GBA": (6032, r["construction_costs"]["gba_sqm"]),
    "Revenue": (93_496_000, r["revenue"]["gross_revenue"]),
    "IRR": (0.0917, r["kpis"]["irr"]),
    "ROE": (0.301, r["kpis"]["roe_total"]),
    "Net Profit": (14_191_025, r["kpis"]["equity_net_profit"]),
}

print(f"{'Metric':<20} {'Al-Malqa':>14} {'Engine':>14} {'Delta':>7}")
print("-" * 57)
for name, (exp, comp) in ref.items():
    delta = abs(comp - exp) / abs(exp) * 100 if exp else 0
    ok = "OK" if delta < 5 else "FAIL"
    if abs(exp) < 1:
        print(f"  {name:<18} {exp:>13.2%} {comp:>13.2%} {delta:>6.1f}% {ok}")
    else:
        print(f"  {name:<18} {exp:>13,} {comp:>13,.0f} {delta:>6.1f}% {ok}")

print(f"\nEquity CF for IRR: {[f'{v:,.0f}' for v in r['cash_flows']['equity_cf_for_irr']]}")
print(f"Land costs: {r['land_costs']}")
