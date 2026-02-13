"""Trace the Al-Malqa IRR gap source."""
from computation_engine import compute_proforma

land = {
    "area_sqm": 3712,
    "regulations": {"max_floors": 2, "far": 1.625, "coverage_ratio": 0.65, "allowed_uses": ["residential"]},
    "building_code_label": "test", "district_name": "test", "municipality": "test",
    "parcel_id": 0, "parcel_number": "0", "plan_number": "0",
    "market": {"srem_market_index": 10712, "trending_districts": []},
}
overrides = {
    "land_price_per_sqm": 13000, "sale_price_per_sqm": 15500,
    "infrastructure_cost_per_sqm": 300, "superstructure_cost_per_sqm": 2500,
    "parking_area_sqm": 0, "far": 1.625, "in_kind_pct": 0.70,
    "fund_period_years": 3, "bank_ltv_pct": 0.667, "interest_rate_pct": 0.08,
    "efficiency_ratio": 1.0, "other_indirect_pct": 0.05,
}
r = compute_proforma(land, overrides)

print("=== DEBT DRAWDOWN ===")
fin = r["financing"]
print(f"  Interest yearly: {fin.get('interest_yearly')}")
print(f"  Total interest (engine): {fin.get('total_interest'):,.0f}")
print(f"  Total interest (ref):    6,493,653")
ref_interest = [1_360_000, 2_560_000, 2_573_653]
print(f"  Ref yearly: {ref_interest}")
print(f"  Ref total:  {sum(ref_interest):,}")

print("\n=== FUND FEES ===")
ff = r["fund_fees"]
ref_fees = 9_394_095
for k, v in ff.items():
    print(f"  {k}: {v:,.0f}")
print(f"  Engine total: {ff['total_fund_fees']:,.0f}")
print(f"  Ref total:    {ref_fees:,}")
print(f"  Delta:        {ff['total_fund_fees'] - ref_fees:,.0f}")

print("\n=== KEY TOTALS ===")
comparisons = [
    ("Land total", r["land_costs"]["total_land_acquisition"], 49_643_360),
    ("Direct cost", r["construction_costs"]["total_direct_cost"], 16_889_600),
    ("Indirect cost", r["construction_costs"]["total_indirect_cost"], 3_177_900 + 844_480 * 2),  # approx
    ("Total construction", r["construction_costs"]["total_construction"], 20_267_520),
    ("Fund fees + interest", ff["total_fund_fees"] + fin["total_interest"] + fin["arrangement_fee"], 9_394_095),
    ("Fund size", r["fund_size"]["total_fund_size"], 79_304_975),
    ("Equity", r["fund_size"]["equity_amount"], 13_355_108),
    ("In-kind", r["fund_size"]["in_kind_contribution"], 33_779_200),
]
for name, engine, ref in comparisons:
    delta = abs(engine - ref) / ref * 100 if ref else 0
    print(f"  {name:<20} engine={engine:>14,.0f}  ref={ref:>14,}  delta={delta:.1f}%")

print("\n=== EQUITY CF FOR IRR ===")
eq_cf = r["cash_flows"]["equity_cf_for_irr"]
ref_cf = [-47_134_308, 0, 0, 61_325_333]
for i, (eng, ref) in enumerate(zip(eq_cf, ref_cf)):
    print(f"  [{i}] engine={eng:>14,.0f}  ref={ref:>14,}  diff={eng-ref:>10,.0f}")
print(f"\n  IRR engine: {r['kpis']['irr']:.4%}")
print(f"  IRR ref:    9.17%")
