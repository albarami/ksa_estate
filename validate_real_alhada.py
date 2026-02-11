"""Validate with REAL Al-Hada parcel (3834663) + Al-Hada financial assumptions."""

import json
from pathlib import Path
from computation_engine import compute_proforma

# Load the real parcel
land = json.loads(Path("test_land_object_3834663.json").read_text(encoding="utf-8"))

print(f"=== Real Al-Hada Parcel ===")
print(f"  Parcel ID: {land['parcel_id']}")
print(f"  Area: {land['area_sqm']:,.0f} m² (Al-Hada Excel says 35,000)")
print(f"  District: {land['district_name']}")
print(f"  Building Code: {land['building_code_label']} (Al-Hada Excel uses mixed-use assumptions)")
print(f"  Geoportal FAR: {land['regulations']['far']}")
print(f"  Geoportal Floors: {land['regulations']['max_floors']}")
print(f"  Geoportal Coverage: {land['regulations']['coverage_ratio']}")
print(f"  Allowed Uses: {land['regulations']['allowed_uses']}")

# Run with Al-Hada's EXACT financial assumptions
# Note: Al-Hada uses FAR 1.5 (GBA=52,500) but Geoportal says FAR 1.2
# The Excel model was built with manual assumptions, not from Geoportal
overrides_alhada = {
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
    "far": 1.5,  # Al-Hada Excel uses 1.5, override Geoportal's 1.2
}

r = compute_proforma(land, overrides_alhada)

# Also run with ACTUAL Geoportal zoning (FAR 1.2, no override)
overrides_actual = {
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
    # No FAR override — uses Geoportal's 1.2
}
r_actual = compute_proforma(land, overrides_actual)

# Compare
ref = {
    "Fund Size": 541_637_996,
    "Equity": 378_304_663,
    "Net Profit": 114_612_004,
    "IRR": 0.0922,
    "ROE": 0.303,
    "Revenue": 656_250_000,
    "GBA": 52_500,
    "Land Total": 264_293_750,
}

print(f"\n{'Metric':<20} {'Al-Hada':>14} {'FAR=1.5':>14} {'FAR=1.2':>14} {'Δ1.5':>7} {'Δ1.2':>7}")
print("-" * 78)

pairs = [
    ("Fund Size", "fund_size.total_fund_size"),
    ("Equity", "fund_size.equity_amount"),
    ("Revenue", "revenue.gross_revenue"),
    ("GBA", "construction_costs.gba_sqm"),
    ("Land Total", "land_costs.total_land_acquisition"),
    ("Net Profit", "kpis.equity_net_profit"),
    ("IRR", "kpis.irr"),
    ("ROE", "kpis.roe_total"),
]

for label, path in pairs:
    expected = ref.get(label, 0)
    parts = path.split(".")
    v15 = r
    v12 = r_actual
    for p in parts:
        v15 = v15.get(p, {}) if isinstance(v15, dict) else 0
        v12 = v12.get(p, {}) if isinstance(v12, dict) else 0

    d15 = abs(v15 - expected) / abs(expected) * 100 if expected else 0
    d12 = abs(v12 - expected) / abs(expected) * 100 if expected else 0

    if abs(expected) < 1:
        print(f"  {label:<18} {expected:>13.4f} {v15:>13.4f} {v12:>13.4f} {d15:>6.1f}% {d12:>6.1f}%")
    else:
        print(f"  {label:<18} {expected:>13,} {v15:>13,.0f} {v12:>13,.0f} {d15:>6.1f}% {d12:>6.1f}%")

print(f"\n  Note: Al-Hada area={land['area_sqm']:,.0f}m² vs Excel 35,000m² (delta: {abs(land['area_sqm']-35000):,.0f}m²)")
print(f"  Note: Geoportal says FAR=1.2 (س 111, residential) but Al-Hada Excel uses FAR=1.5 (mixed-use)")
