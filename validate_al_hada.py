"""Validate computation engine against Al-Hada exact inputs."""

import json
from pathlib import Path
from computation_engine import compute_proforma
from backend.excel_generator import generate_excel

land = {
    "area_sqm": 35000,
    "regulations": {"max_floors": None, "far": 1.5, "coverage_ratio": 0.6, "allowed_uses": ["residential"]},
    "building_code_label": "Al-Hada Test",
    "district_name": "الهدا",
    "municipality": "أمانة منطقة الرياض",
    "parcel_id": 9999999,
    "parcel_number": "TEST",
    "plan_number": "TEST",
    "market": {
        "srem_market_index": 10712,
        "srem_index_change": -3.3,
        "daily_total_transactions": 885,
        "daily_total_value_sar": 677_228_077,
        "daily_avg_price_sqm": 87,
        "trending_districts": [],
    },
    "data_health": {"fields_checked": 15, "fields_populated": 15, "score_pct": 100},
}

overrides = {
    "land_price_per_sqm": 7000,
    "sale_price_per_sqm": 12500,
    "infrastructure_cost_per_sqm": 500,
    "superstructure_cost_per_sqm": 2500,
    "parking_area_sqm": 15000,
    "parking_cost_per_sqm": 2000,
    "fund_period_years": 3,
    "bank_ltv_pct": 0.6666666666,
    "interest_rate_pct": 0.08,
    "efficiency_ratio": 1.0,
}

r = compute_proforma(land, overrides)

# Al-Hada reference values
ref = {
    "Land Total": (264_293_750, r["land_costs"]["total_land_acquisition"]),
    "  - Land Price": (245_000_000, r["land_costs"]["land_price_total"]),
    "  - Brokerage": (6_125_000, r["land_costs"]["brokerage_fee"]),
    "  - Transfer Tax": (12_250_000, r["land_costs"]["transfer_tax"]),
    "  - Brokerage VAT": (918_750, r["land_costs"]["brokerage_vat"]),
    "Direct Cost": (187_500_000, r["construction_costs"]["total_direct_cost"]),
    "  - Infrastructure": (26_250_000, r["construction_costs"]["infrastructure_cost"]),
    "  - Superstructure": (131_250_000, r["construction_costs"]["superstructure_cost"]),
    "  - Parking": (30_000_000, r["construction_costs"]["parking_cost"]),
    "Indirect Cost": (39_375_000, r["construction_costs"]["total_indirect_cost"]),
    "  - Developer Fee": (18_750_000, r["construction_costs"]["developer_fee"]),
    "  - Other Indirect": (11_250_000, r["construction_costs"]["other_indirect"]),
    "  - Contingency": (9_375_000, r["construction_costs"]["contingency"]),
    "Total Construction": (226_875_000, r["construction_costs"]["total_construction"]),
    "Revenue": (656_250_000, r["revenue"]["gross_revenue"]),
    "GBA": (52_500, r["construction_costs"]["gba_sqm"]),
    "Bank Loan": (163_333_333, r["fund_size"]["bank_loan"]),
    "Total Interest": (34_133_333, r["financing"]["total_interest"]),
    "Fund Size": (541_637_996, r["fund_size"]["total_fund_size"]),
    "Equity": (378_304_663, r["fund_size"]["equity_amount"]),
    "Net Profit": (114_612_004, r["kpis"]["equity_net_profit"]),
    "IRR": (0.0922, r["kpis"]["irr"]),
    "ROE": (0.303, r["kpis"]["roe_total"]),
    "ROE Annual": (0.101, r["kpis"]["roe_annualized"]),
}

print(f"{'Metric':<28} {'Al-Hada':>15} {'Engine':>15} {'Delta%':>8}")
print("-" * 68)
all_pass = True
for name, (expected, computed) in ref.items():
    if expected != 0:
        delta = abs(computed - expected) / abs(expected) * 100
    else:
        delta = 0
    status = "OK" if delta < 5 else "FAIL"
    if delta >= 5:
        all_pass = False
    if abs(expected) < 1:
        print(f"  {name:<26} {expected:>14.4f} {computed:>14.4f} {delta:>7.1f}% {status}")
    else:
        print(f"  {name:<26} {expected:>14,} {computed:>14,.0f} {delta:>7.1f}% {status}")

print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILED'}")

# Cash flows
print("\nCash Flows:")
cf = r["cash_flows"]
for i, yr in enumerate(cf["years"]):
    print(f"  Y{yr}: in={cf['inflows_sales'][i]:>14,.0f}  out={cf['outflows_total'][i]:>14,.0f}  net={cf['net_cash_flow'][i]:>14,.0f}")

print("\nEquity CF for IRR:", [f"{v:,.0f}" for v in cf["equity_cf_for_irr"]])

# Generate Excel
xlsx = generate_excel(r, land)
Path("al_hada_validation.xlsx").write_bytes(xlsx)
print(f"\nExcel saved: al_hada_validation.xlsx ({len(xlsx):,} bytes)")

# Save JSON
Path("al_hada_validation_proforma.json").write_text(
    json.dumps(r, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
)
print("JSON saved: al_hada_validation_proforma.json")
