"""Core computation engine for real estate fund pro-forma analysis.

Takes a Land Object (from data_fetch.py) + user overrides and returns
a complete pro-forma with cash flows, KPIs, and sensitivity analysis.

ALL math done by Python/NumPy/numpy-financial — NEVER by the LLM.

Usage:
    from computation_engine import compute_proforma
    result = compute_proforma(land_object, user_overrides)
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import numpy_financial as npf


# ---------------------------------------------------------------------------
# Default assumptions (from computation_template.json)
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, Any] = {
    # Construction
    "infrastructure_cost_per_sqm": 500,
    "superstructure_cost_per_sqm": 2500,
    "parking_area_sqm": 0,
    "parking_cost_per_sqm": 2000,
    "efficiency_ratio": 0.85,

    # Acquisition costs
    "brokerage_fee_pct": 0.025,
    "real_estate_transfer_tax_pct": 0.05,
    "brokerage_vat_pct": 0.15,

    # Soft costs (% of direct construction cost)
    "developer_fee_pct": 0.10,
    "other_indirect_pct": 0.06,
    "contingency_pct": 0.05,

    # Revenue
    "presale_pct": 0.0,
    "absorption_months": 12,

    # Financing
    "bank_ltv_pct": 0.667,
    "interest_rate_pct": 0.08,
    "arrangement_fee_pct": 0.02,

    # Fund structure
    "fund_period_years": 3,
    "cash_purchase_pct": 1.0,
    "in_kind_pct": 0.0,

    # Fund fees
    "management_fee_pct": 0.015,
    "custodian_fee_annual": 50_000,
    "board_fee_annual": 100_000,
    "sharia_certificate_fee": 5_000,
    "sharia_board_fee_annual": 5_000,
    "legal_counsel_fee": 50_000,
    "auditor_fee_annual": 50_000,
    "valuation_fee_quarterly": 20_000,
    "other_reserve_pct": 0.0005,
    "spv_formation_fee": 25_000,
    "structuring_fee_pct": 0.01,
    "operator_fee_pct": 0.0015,

    # Phasing (S-curve, normalised to fund_period_years=3)
    "land_phasing": [1.0, 0.0, 0.0],
    "direct_cost_phasing": [0.33, 0.45, 0.22],
    "indirect_cost_phasing": [0.33, 0.45, 0.22],
    "revenue_phasing": [0.0, 0.0, 1.0],
}


# ---------------------------------------------------------------------------
# Parameter resolution
# ---------------------------------------------------------------------------

def _resolve(
    key: str,
    land_object: dict,
    overrides: dict,
) -> tuple[Any, str]:
    """Resolve a parameter value with priority: override > auto > default.

    Returns:
        (value, source) where source is 'user', 'auto', or 'default'.
    """
    if key in overrides and overrides[key] is not None:
        return overrides[key], "user"

    # Auto-mappings from land_object
    auto_map: dict[str, str] = {
        "land_area_sqm": "area_sqm",
        "max_floors": "regulations.max_floors",
        "far": "regulations.far",
        "coverage_ratio": "regulations.coverage_ratio",
        "allowed_uses": "regulations.allowed_uses",
        "building_code": "building_code_label",
        "district": "district_name",
    }

    if key in auto_map:
        path = auto_map[key]
        obj: Any = land_object
        for part in path.split("."):
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                obj = None
                break
        if obj is not None:
            return obj, "auto"

    if key in DEFAULTS:
        return DEFAULTS[key], "default"

    return None, "missing"


def _get(
    key: str,
    params: dict,
) -> Any:
    """Shortcut to get resolved value from params dict."""
    return params[key]["value"]


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_proforma(
    land_object: dict,
    user_overrides: dict | None = None,
) -> dict[str, Any]:
    """Compute a complete pro-forma from a Land Object + user overrides.

    Args:
        land_object: Output from data_fetch.py (or manual dict).
        user_overrides: Optional dict of parameter overrides.

    Returns:
        ProFormaResult dictionary with all sections.
    """
    overrides = user_overrides or {}

    # ---------------------------------------------------------------
    # 1. Resolve all inputs
    # ---------------------------------------------------------------
    param_keys = [
        "land_area_sqm", "land_price_per_sqm", "sale_price_per_sqm",
        "max_floors", "far", "coverage_ratio", "allowed_uses",
        "building_code", "district",
        "infrastructure_cost_per_sqm", "superstructure_cost_per_sqm",
        "parking_area_sqm", "parking_cost_per_sqm", "efficiency_ratio",
        "brokerage_fee_pct", "real_estate_transfer_tax_pct",
        "brokerage_vat_pct",
        "developer_fee_pct", "other_indirect_pct", "contingency_pct",
        "presale_pct", "absorption_months",
        "bank_ltv_pct", "interest_rate_pct", "arrangement_fee_pct",
        "fund_period_years", "cash_purchase_pct", "in_kind_pct",
        "management_fee_pct", "custodian_fee_annual", "board_fee_annual",
        "sharia_certificate_fee", "sharia_board_fee_annual",
        "legal_counsel_fee", "auditor_fee_annual",
        "valuation_fee_quarterly", "other_reserve_pct",
        "spv_formation_fee", "structuring_fee_pct", "operator_fee_pct",
        "land_phasing", "direct_cost_phasing", "indirect_cost_phasing",
        "revenue_phasing",
    ]

    params: dict[str, dict] = {}
    for key in param_keys:
        val, src = _resolve(key, land_object, overrides)
        params[key] = {"value": val, "source": src}

    # Convenience accessors
    def p(key: str) -> Any:
        return params[key]["value"]

    n_years = int(p("fund_period_years"))

    # Extend phasing arrays if fund period differs from default 3
    def _phase(key: str) -> np.ndarray:
        arr = np.array(p(key), dtype=float)
        if len(arr) < n_years:
            arr = np.pad(arr, (0, n_years - len(arr)))
        elif len(arr) > n_years:
            arr = arr[:n_years]
        # Normalise to sum=1
        s = arr.sum()
        if s > 0:
            arr = arr / s
        return arr

    land_ph = _phase("land_phasing")
    direct_ph = _phase("direct_cost_phasing")
    indirect_ph = _phase("indirect_cost_phasing")
    revenue_ph = _phase("revenue_phasing")

    # ---------------------------------------------------------------
    # 2. Land costs (in-kind aware)
    # ---------------------------------------------------------------
    land_area = float(p("land_area_sqm") or 0)
    land_ppmsq = float(p("land_price_per_sqm") or 0)
    in_kind_pct = float(p("in_kind_pct") or 0)
    cash_pct = 1.0 - in_kind_pct

    land_price_total = land_area * land_ppmsq
    in_kind_value = land_price_total * in_kind_pct

    # Brokerage: ALWAYS on full land price (broker arranged the deal regardless)
    brokerage_fee = p("brokerage_fee_pct") * land_price_total
    brokerage_vat = p("brokerage_vat_pct") * brokerage_fee
    # Transfer tax: 0 when in-kind (contribution, not sale). Full when cash purchase.
    transfer_tax = p("real_estate_transfer_tax_pct") * land_price_total if in_kind_pct == 0 else 0.0

    # Total land includes full price (in-kind is a contribution, not free)
    total_land = land_price_total + brokerage_fee + transfer_tax + brokerage_vat
    cash_land = total_land - in_kind_value

    land_costs = {
        "land_price_total": land_price_total,
        "brokerage_fee": brokerage_fee,
        "transfer_tax": transfer_tax,
        "brokerage_vat": brokerage_vat,
        "total_land_acquisition": total_land,
        "cash_portion": cash_land,
        "in_kind_portion": in_kind_value,
        "in_kind_pct": in_kind_pct,
    }

    # ---------------------------------------------------------------
    # 3. Construction costs
    # ---------------------------------------------------------------
    far_val = float(p("far") or 1.0)
    gba = land_area * far_val
    sellable = gba * p("efficiency_ratio")

    infra_cost = gba * p("infrastructure_cost_per_sqm")
    super_cost = gba * p("superstructure_cost_per_sqm")
    parking_area = float(p("parking_area_sqm") or 0)
    parking_cost = parking_area * p("parking_cost_per_sqm")
    total_direct = infra_cost + super_cost + parking_cost

    dev_fee = p("developer_fee_pct") * total_direct
    other_indirect = p("other_indirect_pct") * total_direct
    contingency = p("contingency_pct") * total_direct
    total_indirect = dev_fee + other_indirect + contingency
    total_construction = total_direct + total_indirect

    construction_costs = {
        "gba_sqm": gba,
        "sellable_area_sqm": sellable,
        "infrastructure_cost": infra_cost,
        "superstructure_cost": super_cost,
        "parking_cost": parking_cost,
        "total_direct_cost": total_direct,
        "developer_fee": dev_fee,
        "other_indirect": other_indirect,
        "contingency": contingency,
        "total_indirect_cost": total_indirect,
        "total_construction": total_construction,
    }

    # ---------------------------------------------------------------
    # 4. Revenue
    # ---------------------------------------------------------------
    sale_ppmsq = float(p("sale_price_per_sqm") or 0)
    gross_revenue = sellable * sale_ppmsq

    revenue = {
        "sellable_area_sqm": sellable,
        "sale_price_per_sqm": sale_ppmsq,
        "gross_revenue": gross_revenue,
        "net_revenue": gross_revenue,
    }

    # ---------------------------------------------------------------
    # 5. Financing
    # ---------------------------------------------------------------
    bank_loan = p("bank_ltv_pct") * land_price_total
    arrangement_fee = p("arrangement_fee_pct") * bank_loan

    financing = {
        "bank_loan_amount": bank_loan,
        "interest_rate_pct": p("interest_rate_pct"),
        "arrangement_fee": arrangement_fee,
    }

    # ---------------------------------------------------------------
    # 6. Fund fees (estimated over full fund period)
    # ---------------------------------------------------------------
    total_cost_base = total_land + total_construction
    n = n_years

    mgmt_fee_total = p("management_fee_pct") * total_cost_base
    custodian_total = p("custodian_fee_annual") * n
    board_total = p("board_fee_annual") * n
    sharia_total = p("sharia_certificate_fee") + p("sharia_board_fee_annual") * n
    legal_total = p("legal_counsel_fee")
    auditor_total = p("auditor_fee_annual") * n
    valuation_total = p("valuation_fee_quarterly") * 4 * n
    reserve_total = p("other_reserve_pct") * total_cost_base
    spv_total = p("spv_formation_fee")
    operator_total = p("operator_fee_pct") * total_cost_base

    # Structuring fee needs equity (circular) — first-pass estimate
    pre_fees = total_land + total_construction
    est_total_fund = pre_fees + bank_loan * p("interest_rate_pct") * n + arrangement_fee
    est_equity = est_total_fund - bank_loan - in_kind_value
    structuring_total = p("structuring_fee_pct") * est_equity

    total_fund_fees = (
        mgmt_fee_total + custodian_total + board_total + sharia_total
        + legal_total + auditor_total + valuation_total + reserve_total
        + spv_total + structuring_total + operator_total
    )

    fund_fees = {
        "management_fee": mgmt_fee_total,
        "custodian_fee": custodian_total,
        "board_fee": board_total,
        "sharia_fees": sharia_total,
        "legal_counsel": legal_total,
        "auditor_fee": auditor_total,
        "valuation_fee": valuation_total,
        "other_reserve": reserve_total,
        "spv_fee": spv_total,
        "structuring_fee": structuring_total,
        "operator_fee": operator_total,
        "total_fund_fees": total_fund_fees,
    }

    # ---------------------------------------------------------------
    # 7. Total interest (year-by-year debt outstanding)
    # ---------------------------------------------------------------
    # Debt drawdown follows what the bank is actually financing:
    # - Cash deals (in_kind=0): bank finances land + construction proportionally
    # - In-kind deals (in_kind>0): bank finances construction only
    #   (land is contributed, not purchased — bank only releases for build costs)
    # Debt drawdown follows cash spending needs each year:
    # - Land cash outflow (total land minus in-kind contribution)
    # - Construction (direct + indirect)
    # This determines when the bank releases funds.
    cash_land_outflow = (total_land - in_kind_value) * land_ph
    construction_yearly = total_direct * direct_ph + total_indirect * indirect_ph
    total_cash_needs = cash_land_outflow + construction_yearly
    spend_share = total_cash_needs / total_cash_needs.sum() if total_cash_needs.sum() > 0 else np.ones(n) / n

    debt_drawdown = bank_loan * spend_share
    debt_outstanding = np.cumsum(debt_drawdown)
    # Repayment in final year
    debt_repayment = np.zeros(n)
    debt_repayment[-1] = bank_loan
    interest_yearly = p("interest_rate_pct") * debt_outstanding
    total_interest = float(interest_yearly.sum())

    financing["total_interest"] = total_interest
    financing["interest_yearly"] = interest_yearly.tolist()

    # ---------------------------------------------------------------
    # 8. Fund size & capital structure
    # ---------------------------------------------------------------
    total_fund_size = (
        total_land + total_construction + total_fund_fees
        + total_interest + arrangement_fee
    )
    equity_amount = total_fund_size - bank_loan - in_kind_value

    fund_size = {
        "total_fund_size": total_fund_size,
        "equity_amount": equity_amount,
        "in_kind_contribution": in_kind_value,
        "bank_loan": bank_loan,
        "equity_pct": equity_amount / total_fund_size if total_fund_size > 0 else 0,
        "debt_pct": bank_loan / total_fund_size if total_fund_size > 0 else 0,
    }

    # ---------------------------------------------------------------
    # 9. Cash flows (year-by-year)
    # ---------------------------------------------------------------
    years = list(range(1, n + 1))

    # Inflows
    sales_cf = gross_revenue * revenue_ph

    # Outflows
    land_cf = total_land * land_ph
    direct_cf = total_direct * direct_ph
    indirect_cf = total_indirect * indirect_ph

    # Annual fund fees (spread based on cost outflows each year)
    cost_per_yr = land_cf + direct_cf + indirect_cf
    cost_share = cost_per_yr / cost_per_yr.sum() if cost_per_yr.sum() > 0 else np.ones(n) / n
    mgmt_cf = p("management_fee_pct") * cost_per_yr

    # Fixed annual fees
    fixed_annual = (
        p("custodian_fee_annual") + p("board_fee_annual")
        + p("sharia_board_fee_annual") + p("auditor_fee_annual")
        + p("valuation_fee_quarterly") * 4
        + p("other_reserve_pct") * cost_per_yr
        + p("operator_fee_pct") * cost_per_yr
    )

    # One-time fees (Y1)
    onetime = np.zeros(n)
    onetime[0] = (
        p("sharia_certificate_fee") + p("legal_counsel_fee")
        + p("spv_formation_fee") + structuring_total + arrangement_fee
    )

    total_outflows = (
        land_cf + direct_cf + indirect_cf
        + interest_yearly + mgmt_cf + fixed_annual + onetime
    )

    net_cf = sales_cf - total_outflows
    cumulative = np.cumsum(net_cf)

    cash_flows = {
        "years": years,
        "inflows_sales": sales_cf.tolist(),
        "outflows_land": land_cf.tolist(),
        "outflows_direct": direct_cf.tolist(),
        "outflows_indirect": indirect_cf.tolist(),
        "outflows_interest": interest_yearly.tolist(),
        "outflows_fees": (mgmt_cf + fixed_annual + onetime).tolist(),
        "outflows_total": total_outflows.tolist(),
        "net_cash_flow": net_cf.tolist(),
        "cumulative": cumulative.tolist(),
    }

    # Debt cash flows
    debt_cf = debt_drawdown.copy()
    debt_repay_cf = np.zeros(n)
    debt_repay_cf[-1] = bank_loan  # repay in final year

    # Cash waterfall (Al-Hada model approach):
    # Each year: beginning_cash + equity_in + debt_in + revenue - outflows - debt_repay
    # Equity is injected at time-0 (before Y1)
    beginning_cash = np.zeros(n)
    net_cash = np.zeros(n)
    for y in range(n):
        cash_in = beginning_cash[y] + debt_drawdown[y] + sales_cf[y]
        cash_out = total_outflows[y] + debt_repay_cf[y]
        net_cash[y] = cash_in - cash_out
        if y + 1 < n:
            beginning_cash[y + 1] = net_cash[y]

    # The equity CF for IRR:
    # Time 0: -(equity + in_kind) — both are real economic investments
    #   Al-Malqa: M41 = -(13.3M equity + 33.8M in_kind) = -47.1M
    #   Al-Hada: M41 = -(378M equity + 0 in_kind) = -378M
    # Y1..Yn-1: 0 (no intermediate distributions)
    # Yn: surplus after all costs and debt repayment
    total_equity_invested = equity_amount + in_kind_value
    equity_cf_for_irr = np.zeros(n + 1)
    equity_cf_for_irr[0] = -total_equity_invested

    # Surplus: all sources in - all uses out - debt repaid
    total_surplus = (
        total_equity_invested + bank_loan
        + gross_revenue
        - float(total_outflows.sum())
        - bank_loan
    )
    equity_cf_for_irr[-1] = total_surplus

    cash_flows["beginning_cash"] = beginning_cash.tolist()
    cash_flows["net_cash_waterfall"] = net_cash.tolist()
    cash_flows["net_equity_cashflows"] = equity_cf_for_irr.tolist()
    cash_flows["equity_cf_for_irr"] = equity_cf_for_irr.tolist()

    # ---------------------------------------------------------------
    # 10. KPIs
    # ---------------------------------------------------------------
    equity_profit = float(equity_cf_for_irr.sum())

    try:
        irr = float(npf.irr(equity_cf_for_irr))
    except Exception:
        irr = None

    roe_total = equity_profit / total_equity_invested if total_equity_invested > 0 else 0
    roe_annual = roe_total / n if n > 0 else 0
    profit_margin = equity_profit / gross_revenue if gross_revenue > 0 else 0
    cost_rev_ratio = total_fund_size / gross_revenue if gross_revenue > 0 else 0
    yield_on_cost = gross_revenue / total_fund_size if total_fund_size > 0 else 0

    kpis = {
        "irr": irr,
        "equity_net_profit": equity_profit,
        "roe_total": roe_total,
        "roe_annualized": roe_annual,
        "profit_margin": profit_margin,
        "cost_to_revenue_ratio": cost_rev_ratio,
        "yield_on_cost": yield_on_cost,
    }

    # ---------------------------------------------------------------
    # 11. Sensitivity analysis (5×5: sale price vs construction cost)
    # ---------------------------------------------------------------
    sensitivity = None
    if "_skip_sensitivity" not in overrides:
        base_sale = sale_ppmsq if sale_ppmsq > 0 else 10000
        base_infra = p("infrastructure_cost_per_sqm")
        base_super = p("superstructure_cost_per_sqm")
        base_cost = base_infra + base_super

        sale_range = np.linspace(base_sale * 0.8, base_sale * 1.2, 5)
        cost_mult = np.linspace(0.8, 1.2, 5)

        sensitivity_irr: list[list[float | None]] = []
        for sp in sale_range:
            row: list[float | None] = []
            for cm in cost_mult:
                try:
                    # Lightweight re-calc: only change revenue and costs
                    adj_infra = base_infra * cm
                    adj_super = base_super * cm
                    adj_direct = gba * (adj_infra + adj_super) + parking_cost
                    adj_indirect = adj_direct * (p("developer_fee_pct") + p("other_indirect_pct") + p("contingency_pct"))
                    adj_constr = adj_direct + adj_indirect
                    adj_revenue = sellable * float(sp)
                    adj_fund = total_land + adj_constr + total_fund_fees + total_interest + arrangement_fee
                    adj_equity = adj_fund - bank_loan - in_kind_value

                    adj_outflows = (
                        total_land * land_ph
                        + adj_direct * direct_ph
                        + adj_indirect * indirect_ph
                        + interest_yearly
                        + (mgmt_cf + fixed_annual + onetime)
                    )
                    adj_total_invested = adj_equity + in_kind_value
                    adj_surplus = adj_total_invested + bank_loan + adj_revenue - float(adj_outflows.sum()) - bank_loan
                    adj_eq_irr = np.zeros(n + 1)
                    adj_eq_irr[0] = -adj_total_invested
                    adj_eq_irr[-1] = adj_surplus
                    row.append(float(npf.irr(adj_eq_irr)))
                except Exception:
                    row.append(None)
            sensitivity_irr.append(row)

        sensitivity = {
            "sale_price_range": sale_range.tolist(),
            "construction_cost_range": (base_cost * cost_mult).tolist(),
            "irr_matrix": sensitivity_irr,
        }

    # ---------------------------------------------------------------
    # 12. Data health
    # ---------------------------------------------------------------
    sources = {k: v["source"] for k, v in params.items()}
    auto_count = sum(1 for s in sources.values() if s == "auto")
    user_count = sum(1 for s in sources.values() if s == "user")
    default_count = sum(1 for s in sources.values() if s == "default")
    missing_count = sum(1 for s in sources.values() if s == "missing")
    total_params = len(sources)
    confidence = (
        (auto_count + user_count) / total_params * 100
        if total_params > 0 else 0
    )

    data_health = {
        "auto": auto_count,
        "user": user_count,
        "default": default_count,
        "missing": missing_count,
        "total_params": total_params,
        "confidence_pct": round(confidence, 1),
        "missing_fields": [k for k, v in params.items() if v["source"] == "missing"],
    }

    # ---------------------------------------------------------------
    # Assemble result
    # ---------------------------------------------------------------
    result = {
        "inputs_used": {k: {"value": v["value"], "source": v["source"]}
                        for k, v in params.items()
                        if not k.endswith("_phasing")},
        "land_costs": land_costs,
        "construction_costs": construction_costs,
        "revenue": revenue,
        "financing": financing,
        "fund_fees": fund_fees,
        "fund_size": fund_size,
        "cash_flows": cash_flows,
        "kpis": kpis,
        "sensitivity": sensitivity,
        "data_health": data_health,
    }

    # Convert numpy types
    return json.loads(json.dumps(result, default=_np_serialize))


def _np_serialize(obj: Any) -> Any:
    """JSON serializer for numpy types."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Not serializable: {type(obj)}")
