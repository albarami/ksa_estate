"""Excel generator replicating Al-Hada Opportunity.xlsx layout exactly.

Sheet 1: Assumptions — exact Al-Hada replica with LIVE formulas
Sheet 2: Zoning Report — parcel + decoded regulations
Sheet 3: Market Data — SREM intelligence
Sheet 4: Sensitivity Analysis — 5x5 IRR matrix
Sheet 5: Scenario Comparison — 3 scenarios side-by-side
"""

from __future__ import annotations

import io
import re
from typing import Any

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side, numbers
from openpyxl.utils import get_column_letter

from backend.excel_labels import get_labels as _L


# ---------------------------------------------------------------------------
# Al-Hada style constants
# ---------------------------------------------------------------------------

FONT_AR = "Sakkal Majalla"
F_NORMAL = Font(name=FONT_AR, size=12)
F_BOLD = Font(name=FONT_AR, size=12, bold=True)
F_HEADER = Font(name=FONT_AR, size=14, bold=True)
F_TOTAL = Font(name=FONT_AR, size=12, bold=True, color="FFFFFF")
F_KPI = Font(name=FONT_AR, size=14, bold=True)
F_SMALL = Font(name=FONT_AR, size=10)
F_LINK = Font(name=FONT_AR, size=10, color="0563C1", underline="single")

FILL_DATA = PatternFill(start_color="FAFBF4", end_color="FAFBF4", fill_type="solid")
FILL_TOTAL = PatternFill(start_color="898989", end_color="898989", fill_type="solid")
FILL_SECTION = PatternFill(start_color="969183", end_color="969183", fill_type="solid")
FILL_GREEN = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")
FILL_RED = PatternFill(start_color="FFCDD2", end_color="FFCDD2", fill_type="solid")
FILL_YELLOW = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")
FILL_HEADER = PatternFill(start_color="1B5E20", end_color="1B5E20", fill_type="solid")

CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
RIGHT_AL = Alignment(horizontal="right", vertical="center")

THIN = Side(style="thin")
MED = Side(style="medium")
BORDER_THIN = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BORDER_TOP_MED = Border(top=MED)

SAR_FMT = '_(* #,##0_);_(* \\(#,##0\\);_(* "-"??_);_(@_)'
SAR2_FMT = '_(* #,##0.00_);_(* \\(#,##0.00\\);_(* "-"??_);_(@_)'
PCT_FMT = "0%"
PCT2_FMT = "0.00%"
PCTD_FMT = "0.0%"
NUM_FMT = '#,##0_);[Red](#,##0)'


def _c(ws, row, col, value=None, font=None, fill=None, fmt=None, align=None, border=None):
    """Write a cell with styling."""
    cell = ws.cell(row=row, column=col)
    if value is not None:
        cell.value = value
    if font:
        cell.font = font
    if fill:
        cell.fill = fill
    if fmt:
        cell.number_format = fmt
    if align:
        cell.alignment = align
    if border:
        cell.border = border
    return cell


# ---------------------------------------------------------------------------
# Sheet 1: Assumptions (Al-Hada exact replica)
# ---------------------------------------------------------------------------

def _build_assumptions_sheet(wb: Workbook, pf: dict, land: dict, L: dict, rtl: bool) -> None:
    """Replicate Al-Hada Assumptions sheet with LIVE formulas."""
    ws = wb.active
    ws.title = L["assumptions"]
    ws.sheet_view.rightToLeft = rtl

    # Column widths (matching Al-Hada)
    widths = {"B": 23, "C": 3, "D": 39, "E": 15, "F": 15, "G": 15, "H": 17, "I": 5,
              "J": 3, "K": 3, "L": 26, "M": 10, "N": 20, "O": 20, "P": 20}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    fs = pf.get("fund_size", {})
    kpis = pf.get("kpis", {})
    rev = pf.get("revenue", {})
    lc = pf.get("land_costs", {})
    cc = pf.get("construction_costs", {})
    ff = pf.get("fund_fees", {})
    fin = pf.get("financing", {})
    cf = pf.get("cash_flows", {})
    inputs = pf.get("inputs_used", {})
    regs = land.get("regulations", {})

    def iv(key):
        return inputs.get(key, {}).get("value")

    n_years = iv("fund_period_years") or 3
    years = list(range(1, int(n_years) + 1))

    # === ROW 2-7: Fund header ===
    _c(ws, 2, 4, "Google Maps Link", F_SMALL)
    _c(ws, 2, 5, f"Parcel {land.get('parcel_id')} - {land.get('district_name')}", F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E2:F2")

    _c(ws, 3, 4, L["fund_name"], F_BOLD, fmt=SAR_FMT)
    _c(ws, 3, 5, L["fund_type_val"], F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E3:F3")
    _c(ws, 3, 12, L["currency"], F_BOLD)

    _c(ws, 4, 4, L["fund_type_label"], F_BOLD, fmt=SAR_FMT)
    _c(ws, 4, 5, L["fund_type_val"], F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E4:F4")
    _c(ws, 4, 12, L["year_label"], F_BOLD)
    for i, yr in enumerate(years):
        _c(ws, 4, 14 + i, 2025 + i, F_BOLD, align=CENTER)

    _c(ws, 5, 4, L["fund_period"], F_BOLD, fmt=SAR_FMT)
    _c(ws, 5, 5, n_years, F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E5:F5")
    for i, yr in enumerate(years):
        _c(ws, 5, 14 + i, f"Y{yr}", F_BOLD, align=CENTER)

    # Fund Size = formula referencing F54
    _c(ws, 6, 4, L["fund_size_label"], F_BOLD, fmt=SAR_FMT)
    _c(ws, 6, 5, "=F54", F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E6:F6")
    _c(ws, 6, 12, L["cf_inflows"], F_BOLD)

    _c(ws, 7, 4, L["total_equity"], F_BOLD, fmt=SAR_FMT)
    _c(ws, 7, 5, "=F57", F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E7:F7")

    # === RIGHT SIDE: Cash Flows Y1..Y3 ===
    _c(ws, 7, 12, L.get("cf_sales", "Sales"), F_NORMAL)
    for i, yr in enumerate(years):
        sales_val = cf.get("inflows_sales", [0]*3)[i] if i < len(cf.get("inflows_sales", [])) else 0
        _c(ws, 7, 14 + i, sales_val, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 8, 12, L.get("total_label", "Total"), F_BOLD)
    for i in range(len(years)):
        _c(ws, 8, 14 + i, f"=SUM({get_column_letter(14+i)}7)", F_BOLD, fmt=SAR_FMT, align=CENTER)

    # === ROW 9: Land section ===
    _c(ws, 9, 2, L["land_section"], F_HEADER, FILL_SECTION)
    _c(ws, 9, 4, L["land_assumptions"], F_HEADER)
    _c(ws, 9, 12, L.get("cf_outflows", "Cash Outflows"), F_BOLD)

    # ROW 10: Column headers
    _c(ws, 10, 6, L.get("total_label", "Total"), F_BOLD, align=CENTER)
    _c(ws, 10, 8, L.get("cash", "Cash"), F_BOLD, align=CENTER)
    _c(ws, 10, 9, L.get("inkind", "In-Kind"), F_BOLD, align=CENTER)

    # ROW 11: Land area + cash/in-kind split
    in_kind_pct = lc.get("in_kind_pct", 0) or 0
    cash_pct = 1.0 - in_kind_pct
    _c(ws, 11, 4, L["land_area"], F_NORMAL)
    _c(ws, 11, 6, land.get("area_sqm", 0), F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 11, 8, cash_pct, F_NORMAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 11, 9, in_kind_pct, F_NORMAL, fmt=PCT_FMT, align=CENTER)

    # Cash flows: land acquisition
    _c(ws, 11, 12, L.get("cf_land", "Land Acquisition"), F_NORMAL)
    for i in range(len(years)):
        land_cf = cf.get("outflows_land", [0]*3)[i] if i < len(cf.get("outflows_land", [])) else 0
        _c(ws, 11, 14 + i, land_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 12: Land price per sqm  → F12 = E12 * F11 (LIVE FORMULA)
    _c(ws, 12, 4, L["land_price"], F_NORMAL)
    _c(ws, 12, 5, iv("land_price_per_sqm") or 0, F_NORMAL, fmt=SAR2_FMT, align=CENTER)
    _c(ws, 12, 6, "=$E$12*F11", F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 12, 8, "=H11*F12", F_NORMAL, fmt=SAR2_FMT, align=CENTER)
    _c(ws, 12, 9, "=I11*F12", F_NORMAL, fmt=SAR2_FMT, align=CENTER)

    # CF: direct costs
    _c(ws, 12, 12, L.get("cf_direct", "Direct Costs"), F_NORMAL)
    for i in range(len(years)):
        d_cf = cf.get("outflows_direct", [0]*3)[i] if i < len(cf.get("outflows_direct", [])) else 0
        _c(ws, 12, 14 + i, d_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 13: Brokerage (on FULL land price — broker is paid regardless)
    _c(ws, 13, 4, L["brokerage"], F_NORMAL)
    _c(ws, 13, 5, iv("brokerage_fee_pct") or 0.025, F_NORMAL, fmt=PCTD_FMT, align=CENTER)
    _c(ws, 13, 6, "=$E$13*F12", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 13, 12, L.get("cf_indirect", "التكاليف غير المباشرة"), F_NORMAL)
    for i in range(len(years)):
        i_cf = cf.get("outflows_indirect", [0]*3)[i] if i < len(cf.get("outflows_indirect", [])) else 0
        _c(ws, 13, 14 + i, i_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 14: Transfer tax (0 when in-kind — contribution, not sale)
    _c(ws, 14, 4, L["transfer_tax"], F_NORMAL)
    _c(ws, 14, 5, iv("real_estate_transfer_tax_pct") or 0.05, F_NORMAL, fmt=PCT_FMT, align=CENTER)
    # Formula: if in-kind > 0, tax = 0; else tax = rate × land
    _c(ws, 14, 6, "=IF(I11>0,0,E14*F12)", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 14, 12, L.get("cf_interest", "Interest"), F_NORMAL)
    for i in range(len(years)):
        int_cf = cf.get("outflows_interest", [0]*3)[i] if i < len(cf.get("outflows_interest", [])) else 0
        _c(ws, 14, 14 + i, int_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 15: Brokerage VAT
    _c(ws, 15, 4, L["brokerage_vat"], F_NORMAL)
    _c(ws, 15, 5, iv("brokerage_vat_pct") or 0.15, F_NORMAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 15, 6, "=E15*F13", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 15, 12, L.get("arrangement_fee", "Arrangement Fee"), F_NORMAL)
    _c(ws, 15, 14, fin.get("arrangement_fee", 0), F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 16: TOTAL LAND = SUM(F12:F15) (LIVE FORMULA)
    _c(ws, 16, 4, L["total"], F_TOTAL, FILL_TOTAL)
    _c(ws, 16, 6, "=SUM(F12:F15)", F_TOTAL, FILL_TOTAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 16, 12, "رسوم إدارة الصندوق ", F_NORMAL)
    for i in range(len(years)):
        fees_cf = cf.get("outflows_fees", [0]*3)[i] if i < len(cf.get("outflows_fees", [])) else 0
        _c(ws, 16, 14 + i, fees_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # === ROW 18: Construction section ===
    _c(ws, 18, 2, L["costs_section"], F_HEADER, FILL_SECTION)
    _c(ws, 18, 4, L["cost_assumptions"], F_HEADER)

    # ROW 19: Headers
    _c(ws, 19, 4, "التكاليف المباشرة ", F_BOLD)
    _c(ws, 19, 5, "%", F_BOLD, align=CENTER)
    _c(ws, 19, 6, "المساحة ", F_BOLD, align=CENTER)
    _c(ws, 19, 7, "التكلفة/ متر ", F_BOLD, align=CENTER)
    _c(ws, 19, 8, "الإجمالي ", F_BOLD, align=CENTER)

    # ROW 20: Infrastructure
    gba = cc.get("gba_sqm", 0)
    _c(ws, 20, 4, "تطوير البنية التحتية", F_NORMAL)
    _c(ws, 20, 5, 1, F_NORMAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 20, 6, gba, F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 20, 7, iv("infrastructure_cost_per_sqm") or 500, F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 20, 8, "=G20*F20", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 21: Superstructure
    _c(ws, 21, 4, "تطوير البنية العلوية", F_NORMAL)
    _c(ws, 21, 6, "=F20", F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 21, 7, iv("superstructure_cost_per_sqm") or 2500, F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 21, 8, "=G21*F21", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 22: Parking
    parking_area = iv("parking_area_sqm") or 0
    _c(ws, 22, 4, "مواقف(قبو)", F_NORMAL)
    _c(ws, 22, 6, parking_area, F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 22, 7, iv("parking_cost_per_sqm") or 2000, F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 22, 8, "=G22*F22", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 23: TOTAL DIRECT = SUM(H20:H22)
    _c(ws, 23, 4, "إجمالي التكاليف المباشرة ", F_TOTAL, FILL_TOTAL)
    _c(ws, 23, 8, "=SUM(H20:H22)", F_TOTAL, FILL_TOTAL, fmt=SAR2_FMT, align=CENTER)

    # ROW 24: Indirect costs header
    _c(ws, 24, 4, "التكاليف غير المباشرة ", F_BOLD)
    _c(ws, 24, 5, "%", F_BOLD, align=CENTER)
    _c(ws, 24, 6, "الإجمالي ", F_BOLD, align=CENTER)

    # ROW 25: Developer fee
    _c(ws, 25, 4, "أتعاب المطور ", F_NORMAL)
    _c(ws, 25, 5, iv("developer_fee_pct") or 0.10, F_NORMAL, fmt=PCTD_FMT, align=CENTER)
    _c(ws, 25, 6, "=E25*H23", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 26: Other indirect
    _c(ws, 26, 4, "تكاليف غير مباشرة أخرى ", F_NORMAL)
    _c(ws, 26, 5, iv("other_indirect_pct") or 0.06, F_NORMAL, fmt=PCTD_FMT, align=CENTER)
    _c(ws, 26, 6, "=E26*H23", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 27: Contingency
    _c(ws, 27, 4, "احتياطي ", F_NORMAL)
    _c(ws, 27, 5, iv("contingency_pct") or 0.05, F_NORMAL, fmt=PCTD_FMT, align=CENTER)
    _c(ws, 27, 6, "=E27*H23", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 28: TOTAL INDIRECT
    _c(ws, 28, 4, "إجمالي التكاليف غير المباشرة ", F_TOTAL, FILL_TOTAL)
    _c(ws, 28, 8, "=F25+F26+F27", F_TOTAL, FILL_TOTAL, fmt=SAR2_FMT, align=CENTER)

    # ROW 29: TOTAL ALL
    _c(ws, 29, 4, "إجمالي التكاليف المباشرة وغير المباشرة ", F_TOTAL, FILL_TOTAL)
    _c(ws, 29, 8, "=H28+H23", F_TOTAL, FILL_TOTAL, fmt=SAR2_FMT, align=CENTER)

    # === RIGHT SIDE: Net cash flows, cumulative, fund structure ===
    _c(ws, 28, 12, "الإجمالي ", F_TOTAL, FILL_TOTAL)
    for i in range(len(years)):
        col = 14 + i
        _c(ws, 28, col, f"=SUM({get_column_letter(col)}11:{get_column_letter(col)}27)", F_TOTAL, FILL_TOTAL, fmt=NUM_FMT, align=CENTER)

    _c(ws, 30, 12, "صافي التدفقات النقدية ", F_BOLD, border=BORDER_TOP_MED)
    for i in range(len(years)):
        col = 14 + i
        _c(ws, 30, col, f"={get_column_letter(col)}8-{get_column_letter(col)}28", F_BOLD, fmt=NUM_FMT, align=CENTER, border=BORDER_TOP_MED)

    _c(ws, 31, 12, "Cumulative Cash Flow", F_NORMAL)
    _c(ws, 31, 14, "=N30", F_NORMAL, fmt=NUM_FMT, align=CENTER)
    if len(years) > 1:
        _c(ws, 31, 15, "=O30+N31", F_NORMAL, fmt=NUM_FMT, align=CENTER)
    if len(years) > 2:
        _c(ws, 31, 16, "=P30+O31", F_NORMAL, fmt=NUM_FMT, align=CENTER)

    # === ROW 31: Sales section ===
    _c(ws, 31, 2, "المبيعات", F_HEADER, FILL_SECTION)
    _c(ws, 31, 4, "افتراضات المبيعات", F_HEADER)
    _c(ws, 31, 5, "%", F_BOLD, align=CENTER)
    _c(ws, 31, 6, "المساحة ", F_BOLD, align=CENTER)
    _c(ws, 31, 7, "قيمة المتر ", F_BOLD, align=CENTER)
    _c(ws, 31, 8, "إجمالي المبيعات ", F_BOLD, align=CENTER)

    # ROW 32: Residential sales
    _c(ws, 32, 4, "بيع وحدات", F_NORMAL)
    _c(ws, 32, 6, "=F20", F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 32, 7, iv("sale_price_per_sqm") or 0, F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 32, 8, "=G32*F32", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 33: TOTAL SALES
    _c(ws, 33, 4, "الإجمالي", F_TOTAL, FILL_TOTAL)
    _c(ws, 33, 8, "=H32", F_TOTAL, FILL_TOTAL, fmt=SAR2_FMT, align=CENTER)

    # === Fund structure (right side) ===
    _c(ws, 33, 12, L.get("cf_fund_capital", "Fund Capital Structure"), F_BOLD)
    _c(ws, 34, 12, L.get("equity", "Equity"), F_NORMAL)
    _c(ws, 34, 14, "=F57", F_NORMAL, fmt=NUM_FMT, align=CENTER)
    _c(ws, 35, 12, L.get("inkind_owner", "In-Kind Contribution"), F_NORMAL)
    _c(ws, 35, 14, "=I12", F_NORMAL, fmt=NUM_FMT, align=CENTER)

    bank_loan = fin.get("bank_loan_amount", 0) if isinstance(fin.get("bank_loan_amount"), (int, float)) else 0
    _c(ws, 36, 12, "Debt Withdrawal", F_NORMAL)
    _c(ws, 36, 14, bank_loan, F_NORMAL, fmt=NUM_FMT, align=CENTER)

    _c(ws, 37, 12, "Debt Outstanding", F_NORMAL)
    _c(ws, 37, 14, "=N36", F_NORMAL, fmt=NUM_FMT, align=CENTER)
    if len(years) > 1:
        _c(ws, 37, 15, "=O36+N37", F_NORMAL, fmt=NUM_FMT, align=CENTER)

    _c(ws, 38, 12, "Debt Repayment", F_NORMAL)
    if len(years) >= 3:
        _c(ws, 38, 16, "=P37", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 40, 12, "Net Cashflows", F_BOLD, border=BORDER_TOP_MED)
    for i in range(len(years)):
        net = cf.get("net_cash_flow", [0]*3)[i] if i < len(cf.get("net_cash_flow", [])) else 0
        _c(ws, 40, 14 + i, net, F_BOLD, fmt=NUM_FMT, align=CENTER, border=BORDER_TOP_MED)

    # Equity cash flow for IRR: initial = -(equity + in_kind)
    equity_amount = fs.get("equity_amount", 0)
    in_kind_contrib = fs.get("in_kind_contribution", 0)
    total_invested = equity_amount + in_kind_contrib
    _c(ws, 41, 12, L.get("cf_net_equity", "Net Equity Cashflow"), F_BOLD)
    _c(ws, 41, 13, -total_invested, F_BOLD, fmt=NUM_FMT, align=CENTER)
    for i in range(len(years)):
        val = 0
        if i == len(years) - 1:
            eq_cf = pf.get("cash_flows", {}).get("equity_cf_for_irr", [])
            if eq_cf and len(eq_cf) > len(years):
                val = eq_cf[-1]
        _c(ws, 41, 14 + i, val, F_BOLD, fmt=SAR_FMT, align=CENTER)

    # === ROW 36: Fund fees section ===
    _c(ws, 36, 2, L.get("financing_section", "Fund Fees"), F_HEADER, FILL_SECTION)
    _c(ws, 36, 4, L.get("total_financing", "Financing & Fund Cost"), F_HEADER)

    _c(ws, 37, 4, " Cost", F_BOLD)
    _c(ws, 37, 6, "Total (SAR)", F_BOLD, align=CENTER)

    fund_fee_rows = [
        (38, "فوائد تمويل ", iv("interest_rate_pct") or 0.08, PCT2_FMT, fin.get("total_interest", 0)),
        (39, "أتعاب ترتيب تمويل ", iv("arrangement_fee_pct") or 0.02, PCT2_FMT, fin.get("arrangement_fee", 0)),
        (40, "رسوم إدارة الصندوق ", iv("management_fee_pct") or 0.015, PCT2_FMT, ff.get("management_fee", 0)),
        (41, "رسوم أمين الحفظ", iv("custodian_fee_annual") or 50000, SAR_FMT, ff.get("custodian_fee", 0)),
        (42, "مجلس الإدارة ", iv("board_fee_annual") or 100000, SAR_FMT, ff.get("board_fee", 0)),
        (43, "إصدار الشهادة الشرعية للصندوق", iv("sharia_certificate_fee") or 5000, SAR_FMT, ff.get("sharia_fees", 0)),
        (44, "أتعاب الهيئة الشرعية ", iv("sharia_board_fee_annual") or 5000, SAR_FMT, ff.get("sharia_fees", 0)),
        (45, "مستشار قانوني", iv("legal_counsel_fee") or 50000, SAR_FMT, ff.get("legal_counsel", 0)),
        (46, "مراجع الحسابات ", iv("auditor_fee_annual") or 50000, SAR_FMT, ff.get("auditor_fee", 0)),
        (47, "التقييم ", iv("valuation_fee_quarterly") or 20000, SAR_FMT, ff.get("valuation_fee", 0)),
        (48, "احتياطي مصروفات أخرى", iv("other_reserve_pct") or 0.0005, PCT2_FMT, ff.get("other_reserve", 0)),
        (49, "رسوم إنشاء الشركة ذات الغرض الخاص", iv("spv_formation_fee") or 25000, SAR_FMT, ff.get("spv_fee", 0)),
        (50, "رسوم هيكلة ", iv("structuring_fee_pct") or 0.01, PCT_FMT, ff.get("structuring_fee", 0)),
        (51, "أتعاب المشغل", iv("operator_fee_pct") or 0.0015, PCT2_FMT, ff.get("operator_fee", 0)),
    ]
    for row, label, rate, rate_fmt, total in fund_fee_rows:
        _c(ws, row, 4, label, F_NORMAL)
        _c(ws, row, 5, rate, F_NORMAL, fmt=rate_fmt, align=CENTER)
        _c(ws, row, 6, total, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 52: TOTAL fund fees
    _c(ws, 52, 4, "Total Financing & Fund Cost", F_TOTAL, FILL_TOTAL)
    _c(ws, 52, 6, "=SUM(F38:F51)", F_TOTAL, FILL_TOTAL, fmt=SAR_FMT, align=CENTER)

    # === KPIs section (right side, below cash flows) ===
    _c(ws, 43, 12, "Project KPIs", F_HEADER, border=BORDER_TOP_MED)

    # IRR = actual Excel IRR formula
    _c(ws, 44, 12, "IRR", F_KPI)
    _c(ws, 44, 14, "=IRR(M41:P41)", F_KPI, fmt=PCT2_FMT, align=CENTER)

    _c(ws, 45, 12, "Equity Net Profit", F_BOLD)
    _c(ws, 45, 14, "=SUM(M41:P41)", F_BOLD, fmt=SAR_FMT, align=CENTER)

    _c(ws, 46, 12, "ROE", F_KPI)
    _c(ws, 46, 14, "=-N45/M41", F_KPI, fmt=PCTD_FMT, align=CENTER)

    _c(ws, 47, 12, "ROE Annualized ", F_BOLD)
    _c(ws, 47, 14, f"=N46/{int(n_years)}", F_BOLD, fmt=PCT2_FMT, align=CENTER)

    # === ROW 54: TOTAL FUND SIZE ===
    _c(ws, 54, 4, "Total Fund Size", F_TOTAL, FILL_TOTAL)
    _c(ws, 54, 6, "=F16+H29+F52", F_TOTAL, FILL_TOTAL, fmt=SAR_FMT, align=CENTER)

    # === ROW 56-60: Capital structure ===
    _c(ws, 56, 4, "Capital Structure", F_HEADER)
    _c(ws, 57, 4, "Equity", F_BOLD)
    _c(ws, 57, 5, "=F57/$F$60", F_NORMAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 57, 6, "=F54-SUM(F58:F59)", F_BOLD, fmt=SAR_FMT, align=CENTER)

    _c(ws, 58, 4, "In-Kind (Land Owner)", F_NORMAL)
    _c(ws, 58, 5, "=F58/$F$60", F_NORMAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 58, 6, "=I12", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    ltv = iv("bank_ltv_pct") or 0.667
    _c(ws, 59, 4, "Bank Financing", F_NORMAL)
    _c(ws, 59, 5, "=F59/$F$60", F_NORMAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 59, 6, f"={ltv}*F12", F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 59, 7, ltv, F_NORMAL, fmt=PCT_FMT, align=CENTER)

    _c(ws, 60, 4, "Total Capital", F_TOTAL, FILL_TOTAL)
    _c(ws, 60, 5, "=SUM(E57:E59)", F_TOTAL, FILL_TOTAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 60, 6, "=SUM(F57:F59)", F_TOTAL, FILL_TOTAL, fmt=SAR_FMT, align=CENTER)

    # Apply data fill to input cells
    for row in range(11, 55):
        for col in [5, 6, 7, 8]:
            cell = ws.cell(row=row, column=col)
            if cell.value is not None and cell.fill == PatternFill():
                cell.fill = FILL_DATA


# ---------------------------------------------------------------------------
# Sheet 2: Zoning Report
# ---------------------------------------------------------------------------

def _build_zoning_sheet(wb: Workbook, land: dict, L: dict, rtl: bool) -> None:
    ws = wb.create_sheet(L.get("zoning_title", "Zoning")[:31])
    ws.sheet_view.rightToLeft = rtl
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["D"].width = 35

    _c(ws, 1, 2, L["zoning_title"], Font(name=FONT_AR, size=16, bold=True, color="FFFFFF"), FILL_HEADER, align=CENTER)
    ws.merge_cells("B1:D1")

    regs = land.get("regulations", {})
    plan_info = land.get("plan_info", {})
    demo = land.get("district_demographics", {})

    items = [
        (L["parcel_no"], land.get("parcel_number")),
        (L["plan_no"], land.get("plan_number")),
        (L["district"], land.get("district_name")),
        (L["municipality"], land.get("municipality")),
        (L["area_label"], land.get("area_sqm")),
        (L["building_code"], land.get("building_code_label")),
        ("", ""),
        (L["max_floors"], regs.get("max_floors")),
        (L["far_label"], regs.get("far")),
        (L["coverage_label"], regs.get("coverage_ratio")),
        (L["allowed_uses"], ", ".join(regs.get("allowed_uses") or [])),
        (L["setbacks_label"], ", ".join(str(v) for v in (regs.get("setback_values_m") or []))),
        (L["primary_use"], land.get("primary_use_label")),
        (L["land_use"], land.get("detailed_use_label")),
    ]

    # Plan info from Geoportal Layer 3
    if plan_info:
        items.append(("", ""))
        items.append(("\u062d\u0627\u0644\u0629 \u0627\u0644\u0645\u062e\u0637\u0637" if rtl else "Plan Status", plan_info.get("plan_status")))
        items.append(("\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0627\u0644\u0645\u062e\u0637\u0637" if rtl else "Plan Use", plan_info.get("plan_use")))
        items.append(("\u0646\u0648\u0639 \u0627\u0644\u0645\u062e\u0637\u0637" if rtl else "Plan Type", plan_info.get("plan_type")))
        items.append(("\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0645\u062e\u0637\u0637" if rtl else "Plan Date (Hijri)", plan_info.get("plan_date_hijri")))

    # District demographics from Geoportal Layer 4
    if demo:
        items.append(("", ""))
        pop = demo.get("population")
        area_m2 = demo.get("area_m2")
        pop_str = f"{int(pop):,}" if pop else None
        items.append(("\u0633\u0643\u0627\u0646 \u0627\u0644\u062d\u064a" if rtl else "District Population", pop_str))
        if area_m2:
            area_km2 = float(area_m2) / 1_000_000
            items.append(("\u0645\u0633\u0627\u062d\u0629 \u0627\u0644\u062d\u064a" if rtl else "District Area", f"{area_km2:.1f} \u0643\u0645\u00b2"))
        en_name = demo.get("district_name_en")
        if en_name:
            items.append(("District Name (EN)", en_name))
    r = 3
    for label, val in items:
        if not label:
            r += 1
            continue
        _c(ws, r, 2, label, F_BOLD, FILL_DATA, align=RIGHT_AL, border=BORDER_THIN)
        cell = _c(ws, r, 4, val, F_NORMAL, align=CENTER, border=BORDER_THIN)
        if isinstance(val, float) and val < 1:
            cell.number_format = PCT2_FMT
        r += 1

    # Notes
    notes = regs.get("notes") or []
    if notes:
        r += 1
        _c(ws, r, 2, L["notes"], F_HEADER)
        r += 1
        for note in notes:
            # Sanitize illegal characters for openpyxl
            clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(note))
            _c(ws, r, 2, clean, F_SMALL, align=Alignment(wrap_text=True))
            ws.merge_cells(f"B{r}:D{r}")
            r += 1


# ---------------------------------------------------------------------------
# Sheet 3: Market Data
# ---------------------------------------------------------------------------

def _build_market_sheet(wb: Workbook, land: dict, pf: dict, L: dict, rtl: bool) -> None:
    ws = wb.create_sheet("Market Data" if not rtl else "\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0633\u0648\u0642")
    ws.sheet_view.rightToLeft = rtl
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 5
    ws.column_dimensions["D"].width = 25
    ws.column_dimensions["E"].width = 18

    _c(ws, 1, 2, L["market_title"], Font(name=FONT_AR, size=16, bold=True, color="FFFFFF"), FILL_HEADER, align=CENTER)
    ws.merge_cells("B1:E1")

    mkt = land.get("market", {})
    items = [
        (L["market_index"], mkt.get("srem_market_index")),
        (L["market_change"], mkt.get("srem_index_change")),
        (L["daily_transactions"], mkt.get("daily_total_transactions")),
        (L["daily_value"], mkt.get("daily_total_value_sar")),
        (L["avg_price"], mkt.get("daily_avg_price_sqm")),
    ]
    r = 3
    for label, val in items:
        _c(ws, r, 2, label, F_BOLD, FILL_DATA, align=RIGHT_AL, border=BORDER_THIN)
        _c(ws, r, 4, val, F_NORMAL, fmt=SAR_FMT if isinstance(val, (int, float)) and val and val > 100 else "0.00", align=CENTER, border=BORDER_THIN)
        r += 1

    # District-specific market data
    dist_mkt = mkt.get("district", {})
    if dist_mkt:
        r += 1
        dist_label = "\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u062d\u064a" if rtl else "District Market Data"
        _c(ws, r, 2, dist_label, F_HEADER)
        r += 1
        dist_items = [
            ("\u0627\u0644\u062d\u064a" if rtl else "District", dist_mkt.get("district_name")),
            ("\u0645\u062a\u0648\u0633\u0637 \u0627\u0644\u0633\u0639\u0631 / \u0645\u00b2" if rtl else "Avg Price / m\u00b2", dist_mkt.get("avg_price_sqm")),
            ("\u0627\u0644\u0641\u062a\u0631\u0629" if rtl else "Period", dist_mkt.get("period")),
            ("\u0639\u062f\u062f \u0627\u0644\u0635\u0641\u0642\u0627\u062a" if rtl else "Total Deals", dist_mkt.get("total_deals")),
            ("\u0645\u062a\u0648\u0633\u0637 \u0627\u0644\u0631\u064a\u0627\u0636" if rtl else "Riyadh City Avg", dist_mkt.get("city_avg_price_sqm")),
        ]
        for label, val in dist_items:
            if val is not None:
                _c(ws, r, 2, label, F_BOLD, FILL_DATA, align=RIGHT_AL, border=BORDER_THIN)
                fmt = SAR_FMT if isinstance(val, (int, float)) and val and val > 100 else None
                _c(ws, r, 4, val, F_NORMAL, fmt=fmt, align=CENTER, border=BORDER_THIN)
                r += 1

    # Index history
    idx_hist = dist_mkt.get("index_history", []) if dist_mkt else []
    if idx_hist:
        r += 1
        _c(ws, r, 2, "\u0645\u0624\u0634\u0631 \u0627\u0644\u0633\u0648\u0642 (\u0623\u0633\u0628\u0648\u0639\u064a)" if rtl else "Weekly Market Index", F_HEADER)
        r += 1
        _c(ws, r, 2, "\u0627\u0644\u062a\u0627\u0631\u064a\u062e" if rtl else "Date", F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        _c(ws, r, 4, "\u0627\u0644\u0645\u0624\u0634\u0631" if rtl else "Index", F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        _c(ws, r, 5, "\u0627\u0644\u062a\u063a\u064a\u0631" if rtl else "Change", F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        r += 1
        for pt in idx_hist:
            _c(ws, r, 2, pt.get("date", ""), F_NORMAL, align=CENTER, border=BORDER_THIN)
            _c(ws, r, 4, pt.get("index"), F_NORMAL, fmt=SAR_FMT, align=CENTER, border=BORDER_THIN)
            change = pt.get("change", 0)
            cell = _c(ws, r, 5, change, F_NORMAL, fmt="0.00", align=CENTER, border=BORDER_THIN)
            if change and change >= 0:
                cell.fill = FILL_GREEN
            elif change and change < 0:
                cell.fill = FILL_RED
            r += 1

    # Intelligence KPIs
    kpis = pf.get("kpis", {})
    if kpis.get("deal_score") is not None:
        r += 1
        _c(ws, r, 2, "\u062a\u062d\u0644\u064a\u0644 \u0627\u0644\u0635\u0641\u0642\u0629" if rtl else "Deal Analysis", F_HEADER)
        r += 1
        intel_items = [
            ("\u062a\u0642\u064a\u064a\u0645 \u0627\u0644\u0635\u0641\u0642\u0629" if rtl else "Deal Score", f"{kpis['deal_score']}/100"),
            ("\u0646\u0642\u0637\u0629 \u0627\u0644\u062a\u0639\u0627\u062f\u0644" if rtl else "Break-even Price", f"{kpis.get('break_even_price_sqm', 0):,.0f} \u0631.\u0633/\u0645\u00b2"),
            ("\u062a\u0643\u0644\u0641\u0629 \u0627\u0644\u0623\u0631\u0636/\u0645\u00b2 \u0645\u0628\u0646\u064a" if rtl else "Land Cost per GBA", f"{kpis.get('land_cost_per_gba', 0):,.0f} \u0631.\u0633"),
            ("\u0645\u0636\u0627\u0639\u0641 \u0627\u0644\u0639\u0627\u0626\u062f" if rtl else "Revenue Multiple", f"{kpis.get('revenue_multiple', 0):.2f}x"),
            ("\u0646\u0633\u0628\u0629 \u0631\u0633\u0648\u0645 \u0627\u0644\u0635\u0646\u062f\u0648\u0642" if rtl else "Fund Overhead", f"{kpis.get('fund_overhead_ratio', 0)*100:.1f}%"),
        ]
        for label, val in intel_items:
            _c(ws, r, 2, label, F_BOLD, FILL_DATA, align=RIGHT_AL, border=BORDER_THIN)
            _c(ws, r, 4, val, F_NORMAL, align=CENTER, border=BORDER_THIN)
            r += 1

        # Risk flags
        risks = kpis.get("risk_flags", [])
        if risks:
            r += 1
            _c(ws, r, 2, "\u0645\u062e\u0627\u0637\u0631" if rtl else "Risk Flags", F_BOLD)
            r += 1
            for flag in risks:
                _c(ws, r, 2, flag, F_NORMAL, FILL_RED, border=BORDER_THIN)
                r += 1

    # Trending districts
    trending = mkt.get("trending_districts") or []
    if trending:
        r += 2
        _c(ws, r, 2, L["trending_title"], F_HEADER)
        r += 1
        _c(ws, r, 2, L["district"], F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        _c(ws, r, 3, L["city"], F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        _c(ws, r, 4, L["deals"], F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        _c(ws, r, 5, L["value_sar"], F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        r += 1
        for d in trending:
            _c(ws, r, 2, d.get("name"), F_NORMAL, align=CENTER, border=BORDER_THIN)
            _c(ws, r, 3, d.get("city"), F_NORMAL, align=CENTER, border=BORDER_THIN)
            _c(ws, r, 4, d.get("deals"), F_NORMAL, align=CENTER, border=BORDER_THIN)
            _c(ws, r, 5, d.get("total_sar"), F_NORMAL, fmt=SAR_FMT, align=CENTER, border=BORDER_THIN)
            r += 1

    # Data sources
    sources = land.get("data_sources", {})
    if sources:
        r += 2
        _c(ws, r, 2, "\u0645\u0635\u0627\u062f\u0631 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a" if rtl else "Data Sources", F_HEADER)
        r += 1
        for src, active in sources.items():
            status = "\u2705 \u0646\u0634\u0637" if active else "\u274c \u063a\u064a\u0631 \u0645\u062a\u0627\u062d"
            _c(ws, r, 2, src.replace("_", " "), F_NORMAL, border=BORDER_THIN)
            cell = _c(ws, r, 4, status, F_NORMAL, align=CENTER, border=BORDER_THIN)
            cell.fill = FILL_GREEN if active else FILL_RED
            r += 1

    r += 2
    _c(ws, r, 2, L["market_source"], F_SMALL)


# ---------------------------------------------------------------------------
# Sheet 4: Sensitivity
# ---------------------------------------------------------------------------

def _build_sensitivity_sheet(wb: Workbook, pf: dict, L: dict, rtl: bool) -> None:
    ws = wb.create_sheet("Sensitivity" if not rtl else "تحليل الحساسية")
    ws.sheet_view.rightToLeft = rtl

    sens = pf.get("sensitivity")
    if not sens:
        _c(ws, 2, 2, "لا تتوفر بيانات", F_NORMAL)
        return

    _c(ws, 1, 2, "تحليل الحساسية - معدل العائد الداخلي (IRR)", Font(name=FONT_AR, size=16, bold=True, color="FFFFFF"), FILL_HEADER, align=CENTER)
    ws.merge_cells("B1:G1")

    sale_range = sens["sale_price_range"]
    cost_range = sens["construction_cost_range"]
    matrix = sens["irr_matrix"]

    ws.column_dimensions["B"].width = 18
    for i in range(len(cost_range)):
        ws.column_dimensions[get_column_letter(3 + i)].width = 14

    _c(ws, 3, 2, "سعر البيع ↓ \\ التكلفة →", F_BOLD, align=CENTER)
    for i, c in enumerate(cost_range):
        _c(ws, 3, 3 + i, c, F_BOLD, fmt="#,##0", align=CENTER, border=BORDER_THIN)

    for ri, sp in enumerate(sale_range):
        r = 4 + ri
        _c(ws, r, 2, sp, F_BOLD, fmt="#,##0", align=CENTER, border=BORDER_THIN)
        for ci, irr in enumerate(matrix[ri]):
            cell = _c(ws, r, 3 + ci, irr, F_NORMAL, fmt=PCT2_FMT, align=CENTER, border=BORDER_THIN)
            if irr is not None:
                if irr >= 0.10:
                    cell.fill = FILL_GREEN
                elif irr >= 0:
                    cell.fill = FILL_YELLOW
                else:
                    cell.fill = FILL_RED


# ---------------------------------------------------------------------------
# Sheet 5: Scenario Comparison
# ---------------------------------------------------------------------------

def _build_scenario_sheet(wb: Workbook, pf: dict, land: dict, L: dict, rtl: bool) -> None:
    ws = wb.create_sheet("Scenarios" if not rtl else "مقارنة السيناريوهات")
    ws.sheet_view.rightToLeft = rtl
    ws.column_dimensions["B"].width = 25
    for c in ["C", "D", "E"]:
        ws.column_dimensions[c].width = 22

    _c(ws, 1, 2, "مقارنة السيناريوهات", Font(name=FONT_AR, size=16, bold=True, color="FFFFFF"), FILL_HEADER, align=CENTER)
    ws.merge_cells("B1:E1")

    sale_base = pf.get("inputs_used", {}).get("sale_price_per_sqm", {}).get("value", 8000) or 8000
    scenarios = [
        ("متحفظ", 0.8),
        ("أساسي", 1.0),
        ("جريء", 1.3),
    ]

    _c(ws, 3, 2, "السيناريو", F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
    for i, (name, _) in enumerate(scenarios):
        _c(ws, 3, 3 + i, name, F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)

    _c(ws, 4, 2, "سعر البيع / م²", F_NORMAL, align=CENTER, border=BORDER_THIN)
    for i, (_, mult) in enumerate(scenarios):
        _c(ws, 4, 3 + i, sale_base * mult, F_NORMAL, fmt=SAR_FMT, align=CENTER, border=BORDER_THIN)

    # KPI rows (using pre-computed values since we can't run the engine in Excel)
    kpi_rows = [
        ("حجم الصندوق", "total_fund_size"),
        ("حقوق الملكية", "equity_amount"),
        ("معدل العائد الداخلي", "irr"),
        ("العائد على الملكية", "roe_total"),
        ("صافي الربح", "equity_net_profit"),
    ]

    # We only have the base scenario pre-computed, so note it
    fs = pf.get("fund_size", {})
    kpis_data = pf.get("kpis", {})
    r = 5
    for label, key in kpi_rows:
        _c(ws, r, 2, label, F_BOLD, FILL_DATA, align=CENTER, border=BORDER_THIN)
        for i in range(3):
            if i == 1:  # base scenario - use actual values
                val = fs.get(key) if key in ("total_fund_size", "equity_amount") else kpis_data.get(key)
                fmt = PCT2_FMT if key in ("irr", "roe_total") else SAR_FMT
            else:
                val = "—"
                fmt = None
            _c(ws, r, 3 + i, val, F_NORMAL, fmt=fmt, align=CENTER, border=BORDER_THIN)
        r += 1

    r += 1
    _c(ws, r, 2, "* السيناريوهات المتحفظة والجريئة تتطلب إعادة حساب كامل", F_SMALL)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_excel(result: dict, land_object: dict, lang: str = "ar") -> bytes:
    """Generate a professional .xlsx with 5 sheets.

    Args:
        result: ProFormaResult from computation_engine.
        land_object: Land Object from data_fetch.
        lang: 'ar' for Arabic (default), 'en' for English.
    """
    wb = Workbook()
    L = _L(lang)
    rtl = (lang == "ar")

    _build_assumptions_sheet(wb, result, land_object, L, rtl)
    _build_zoning_sheet(wb, land_object, L, rtl)
    _build_market_sheet(wb, land_object, result, L, rtl)
    _build_sensitivity_sheet(wb, result, L, rtl)
    _build_scenario_sheet(wb, result, land_object, L, rtl)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
