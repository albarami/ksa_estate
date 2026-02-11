"""Test the computation engine against Al-Hada reference and parcel 3710897."""

import json
from pathlib import Path

from computation_engine import compute_proforma


def test_al_hada_validation():
    """Validate against Al-Hada reference values from the Excel model."""
    print("=" * 60)
    print("TEST 1: Al-Hada Reference Validation")
    print("=" * 60)

    # Simulate a land object matching Al-Hada inputs
    land_object = {
        "area_sqm": 35000,
        "regulations": {
            "max_floors": None,
            "far": 1.5,
            "coverage_ratio": 0.6,
            "allowed_uses": ["residential"],
        },
        "building_code_label": "test",
        "district_name": "الهدا",
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
        "efficiency_ratio": 1.0,
    }

    result = compute_proforma(land_object, overrides)

    # Expected values from Al-Hada Excel
    expected = {
        "total_fund_size": 541_637_996,
        "equity_amount": 378_304_663,
        "irr": 0.0922,
        "roe_total": 0.303,
        "net_profit": 114_612_004,
    }

    print(f"\n{'Metric':<30} {'Expected':>15} {'Computed':>15} {'Delta%':>10}")
    print("-" * 70)

    checks = [
        ("Total Fund Size", expected["total_fund_size"], result["fund_size"]["total_fund_size"]),
        ("Equity Amount", expected["equity_amount"], result["fund_size"]["equity_amount"]),
        ("Net Profit", expected["net_profit"], result["kpis"]["equity_net_profit"]),
        ("ROE Total", expected["roe_total"], result["kpis"]["roe_total"]),
    ]
    if result["kpis"]["irr"] is not None:
        checks.append(("IRR", expected["irr"], result["kpis"]["irr"]))

    all_pass = True
    for name, exp, comp in checks:
        if exp != 0:
            delta = abs(comp - exp) / abs(exp) * 100
        else:
            delta = 0
        status = "PASS" if delta < 5 else "FAIL"
        if delta >= 5:
            all_pass = False
        if isinstance(exp, float) and abs(exp) < 1:
            print(f"  {name:<28} {exp:>14.4f} {comp:>14.4f} {delta:>9.1f}% {status}")
        else:
            print(f"  {name:<28} {exp:>14,.0f} {comp:>14,.0f} {delta:>9.1f}% {status}")

    print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILED'}")

    # Print key breakdowns
    print(f"\n  Land costs: {result['land_costs']['total_land_acquisition']:,.0f}")
    print(f"  Construction: {result['construction_costs']['total_construction']:,.0f}")
    print(f"  Fund fees: {result['fund_fees']['total_fund_fees']:,.0f}")
    print(f"  Interest: {result['financing']['total_interest']:,.0f}")
    print(f"  Revenue: {result['revenue']['gross_revenue']:,.0f}")
    print(f"  Bank loan: {result['fund_size']['bank_loan']:,.0f}")
    print(f"  Equity %: {result['fund_size']['equity_pct']:.1%}")
    print(f"  Debt %: {result['fund_size']['debt_pct']:.1%}")

    return result


def test_parcel_3710897():
    """Test with real parcel 3710897 data from data_fetch.py."""
    print("\n" + "=" * 60)
    print("TEST 2: Real Parcel 3710897")
    print("=" * 60)

    land_file = Path("test_land_object_3710897.json")
    if not land_file.exists():
        print("  SKIP: test_land_object_3710897.json not found")
        print("  Run: python data_fetch.py 3710897")
        return None

    land_object = json.loads(land_file.read_text(encoding="utf-8"))

    # User provides market assumptions
    overrides = {
        "land_price_per_sqm": 5000,
        "sale_price_per_sqm": 8000,
        "infrastructure_cost_per_sqm": 500,
        "superstructure_cost_per_sqm": 2500,
        "parking_area_sqm": 0,
        "fund_period_years": 3,
    }

    result = compute_proforma(land_object, overrides)

    print(f"\n  Parcel: {land_object.get('parcel_id')}")
    print(f"  District: {land_object.get('district_name')}")
    print(f"  Building code: {land_object.get('building_code_label')}")
    print(f"  Area: {land_object.get('area_sqm'):,.0f} m²")
    print(f"  FAR (auto): {result['inputs_used']['far']['value']}")
    print(f"  Max floors (auto): {result['inputs_used']['max_floors']['value']}")

    print(f"\n  --- PRO-FORMA ---")
    print(f"  GBA: {result['construction_costs']['gba_sqm']:,.0f} m²")
    print(f"  Sellable: {result['revenue']['sellable_area_sqm']:,.0f} m²")
    print(f"  Land cost: {result['land_costs']['total_land_acquisition']:,.0f} SAR")
    print(f"  Construction: {result['construction_costs']['total_construction']:,.0f} SAR")
    print(f"  Revenue: {result['revenue']['gross_revenue']:,.0f} SAR")
    print(f"  Fund size: {result['fund_size']['total_fund_size']:,.0f} SAR")
    print(f"  Equity: {result['fund_size']['equity_amount']:,.0f} SAR ({result['fund_size']['equity_pct']:.0%})")
    print(f"  Bank loan: {result['fund_size']['bank_loan']:,.0f} SAR ({result['fund_size']['debt_pct']:.0%})")

    print(f"\n  --- KPIs ---")
    irr = result["kpis"]["irr"]
    print(f"  IRR: {irr:.2%}" if irr else "  IRR: N/A")
    print(f"  ROE total: {result['kpis']['roe_total']:.1%}")
    print(f"  ROE annualised: {result['kpis']['roe_annualized']:.2%}")
    print(f"  Net profit: {result['kpis']['equity_net_profit']:,.0f} SAR")
    print(f"  Yield on cost: {result['kpis']['yield_on_cost']:.2f}x")

    print(f"\n  --- CASH FLOWS ---")
    for i, yr in enumerate(result["cash_flows"]["years"]):
        print(
            f"  Y{yr}: in={result['cash_flows']['inflows_sales'][i]:>14,.0f}  "
            f"out={result['cash_flows']['outflows_total'][i]:>14,.0f}  "
            f"net={result['cash_flows']['net_cash_flow'][i]:>14,.0f}  "
            f"cum={result['cash_flows']['cumulative'][i]:>14,.0f}"
        )

    print(f"\n  --- SENSITIVITY (IRR) ---")
    if result.get("sensitivity"):
        s = result["sensitivity"]
        header = "Sale\\Cost"
        for c in s["construction_cost_range"]:
            header += f"  {c:>8,.0f}"
        print(f"  {header}")
        for i, sp in enumerate(s["sale_price_range"]):
            row = f"  {sp:>8,.0f}"
            for j, irr_val in enumerate(s["irr_matrix"][i]):
                if irr_val is not None:
                    row += f"  {irr_val:>8.1%}"
                else:
                    row += f"  {'N/A':>8}"
            print(row)

    print(f"\n  --- DATA HEALTH ---")
    dh = result["data_health"]
    print(f"  Auto: {dh['auto']}, User: {dh['user']}, Default: {dh['default']}, Missing: {dh['missing']}")
    print(f"  Confidence: {dh['confidence_pct']:.0f}%")
    if dh["missing_fields"]:
        print(f"  Missing: {dh['missing_fields']}")

    # Save
    out = Path("proforma_3710897.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Saved: {out}")

    return result


if __name__ == "__main__":
    r1 = test_al_hada_validation()
    r2 = test_parcel_3710897()
