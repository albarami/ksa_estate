"""Excel generator replicating Al-Hada Opportunity.xlsx layout exactly.

Sheet 1: Assumptions — exact Al-Hada replica with LIVE formulas
Sheet 2: Zoning Report — parcel + decoded regulations
Sheet 3: Market Data — SREM intelligence
Sheet 4: Sensitivity Analysis — 5x5 IRR matrix
Sheet 5: Scenario Comparison — 3 scenarios side-by-side
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side, numbers
from openpyxl.utils import get_column_letter

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

def _build_assumptions_sheet(wb: Workbook, pf: dict, land: dict) -> None:
    """Replicate Al-Hada Assumptions sheet with LIVE formulas."""
    ws = wb.active
    ws.title = "Assumptions"
    ws.sheet_view.rightToLeft = True

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

    _c(ws, 3, 4, "Fund Name ", F_BOLD, fmt=SAR_FMT)
    _c(ws, 3, 5, "صندوق استثمار عقاري", F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E3:F3")
    _c(ws, 3, 12, "بالريال السعودي", F_BOLD)

    _c(ws, 4, 4, "Fund Type ", F_BOLD, fmt=SAR_FMT)
    _c(ws, 4, 5, "صندوق استثمار عقاري خاص", F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E4:F4")
    _c(ws, 4, 12, "السنة", F_BOLD)
    for i, yr in enumerate(years):
        _c(ws, 4, 14 + i, 2025 + i, F_BOLD, align=CENTER)

    _c(ws, 5, 4, "Fund Period- year", F_BOLD, fmt=SAR_FMT)
    _c(ws, 5, 5, n_years, F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E5:F5")
    for i, yr in enumerate(years):
        _c(ws, 5, 14 + i, f"Y{yr}", F_BOLD, align=CENTER)

    # Fund Size = formula referencing F54
    _c(ws, 6, 4, "Fund Size- SAR", F_BOLD, fmt=SAR_FMT)
    _c(ws, 6, 5, "=F54", F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E6:F6")
    _c(ws, 6, 12, "التدفقات النقدية الداخلة ", F_BOLD)

    _c(ws, 7, 4, "Total Equity", F_BOLD, fmt=SAR_FMT)
    _c(ws, 7, 5, "=F57", F_BOLD, fmt=SAR_FMT)
    ws.merge_cells("E7:F7")

    # === RIGHT SIDE: Cash Flows Y1..Y3 ===
    _c(ws, 7, 12, "المبيعات ", F_NORMAL)
    for i, yr in enumerate(years):
        sales_val = cf.get("inflows_sales", [0]*3)[i] if i < len(cf.get("inflows_sales", [])) else 0
        _c(ws, 7, 14 + i, sales_val, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 8, 12, "الإجمالي ", F_BOLD)
    for i in range(len(years)):
        _c(ws, 8, 14 + i, f"=SUM({get_column_letter(14+i)}7)", F_BOLD, fmt=SAR_FMT, align=CENTER)

    # === ROW 9: Land section ===
    _c(ws, 9, 2, "الأرض", F_HEADER, FILL_SECTION)
    _c(ws, 9, 4, "افتراضات الأرض", F_HEADER)
    _c(ws, 9, 12, "التدفقات النقدية الخارجة ", F_BOLD)

    # ROW 10: Column headers
    _c(ws, 10, 6, "الإجمالي ", F_BOLD, align=CENTER)
    _c(ws, 10, 8, "النقدي", F_BOLD, align=CENTER)
    _c(ws, 10, 9, "العيني ", F_BOLD, align=CENTER)

    # ROW 11: Land area
    _c(ws, 11, 4, "مساحة الأرض ", F_NORMAL)
    _c(ws, 11, 6, land.get("area_sqm", 0), F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 11, 8, iv("cash_purchase_pct") or 1, F_NORMAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 11, 9, iv("in_kind_pct") or 0, F_NORMAL, fmt=PCT_FMT, align=CENTER)

    # Cash flows: land acquisition
    _c(ws, 11, 12, "إجمالي الاستحواذ على الأرض ", F_NORMAL)
    for i in range(len(years)):
        land_cf = cf.get("outflows_land", [0]*3)[i] if i < len(cf.get("outflows_land", [])) else 0
        _c(ws, 11, 14 + i, land_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 12: Land price per sqm  → F12 = E12 * F11 (LIVE FORMULA)
    _c(ws, 12, 4, "سعر الاستحواذ بالمتر ", F_NORMAL)
    _c(ws, 12, 5, iv("land_price_per_sqm") or 0, F_NORMAL, fmt=SAR2_FMT, align=CENTER)
    _c(ws, 12, 6, "=$E$12*F11", F_NORMAL, fmt=SAR_FMT, align=CENTER)
    _c(ws, 12, 8, "=H11*$F$16", F_NORMAL, fmt=SAR2_FMT, align=CENTER)
    _c(ws, 12, 9, "=I11*F12", F_NORMAL, fmt=SAR2_FMT, align=CENTER)

    # CF: direct costs
    _c(ws, 12, 12, "التكاليف المباشرة ", F_NORMAL)
    for i in range(len(years)):
        d_cf = cf.get("outflows_direct", [0]*3)[i] if i < len(cf.get("outflows_direct", [])) else 0
        _c(ws, 12, 14 + i, d_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 13: Brokerage
    _c(ws, 13, 4, "السعي", F_NORMAL)
    _c(ws, 13, 5, iv("brokerage_fee_pct") or 0.025, F_NORMAL, fmt=PCTD_FMT, align=CENTER)
    _c(ws, 13, 6, "=$E$13*F12", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 13, 12, "التكاليف غير المباشرة ", F_NORMAL)
    for i in range(len(years)):
        i_cf = cf.get("outflows_indirect", [0]*3)[i] if i < len(cf.get("outflows_indirect", [])) else 0
        _c(ws, 13, 14 + i, i_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 14: Transfer tax
    _c(ws, 14, 4, "ضريبة التصرفات العقارية", F_NORMAL)
    _c(ws, 14, 5, iv("real_estate_transfer_tax_pct") or 0.05, F_NORMAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 14, 6, "=E14*F12", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 14, 12, "فوائد تمويل ", F_NORMAL)
    for i in range(len(years)):
        int_cf = cf.get("outflows_interest", [0]*3)[i] if i < len(cf.get("outflows_interest", [])) else 0
        _c(ws, 14, 14 + i, int_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 15: Brokerage VAT
    _c(ws, 15, 4, "ضريبة السعي", F_NORMAL)
    _c(ws, 15, 5, iv("brokerage_vat_pct") or 0.15, F_NORMAL, fmt=PCT_FMT, align=CENTER)
    _c(ws, 15, 6, "=E15*F13", F_NORMAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 15, 12, "أتعاب ترتيب تمويل ", F_NORMAL)
    _c(ws, 15, 14, fin.get("arrangement_fee", 0), F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # ROW 16: TOTAL LAND = SUM(F12:F15) (LIVE FORMULA)
    _c(ws, 16, 4, "الإجمالي", F_TOTAL, FILL_TOTAL)
    _c(ws, 16, 6, "=SUM(F12:F15)", F_TOTAL, FILL_TOTAL, fmt=SAR_FMT, align=CENTER)

    _c(ws, 16, 12, "رسوم إدارة الصندوق ", F_NORMAL)
    for i in range(len(years)):
        fees_cf = cf.get("outflows_fees", [0]*3)[i] if i < len(cf.get("outflows_fees", [])) else 0
        _c(ws, 16, 14 + i, fees_cf, F_NORMAL, fmt=SAR_FMT, align=CENTER)

    # === ROW 18: Construction section ===
    _c(ws, 18, 2, "التكاليف", F_HEADER, FILL_SECTION)
    _c(ws, 18, 4, "افتراضات التكاليف ", F_HEADER)

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
    _c(ws, 33, 12, "تمويل رأس مال الصندوق", F_BOLD)
    _c(ws, 34, 12, "Equity", F_NORMAL)
    _c(ws, 34, 14, "=F57", F_NORMAL, fmt=NUM_FMT, align=CENTER)
    _c(ws, 35, 12, "In-Kind Contribution", F_NORMAL)
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

    # Equity cash flow for IRR
    equity_amount = fs.get("equity_amount", 0)
    _c(ws, 41, 12, "Net Equity Cashflow", F_BOLD)
    _c(ws, 41, 13, -equity_amount, F_BOLD, fmt=NUM_FMT, align=CENTER)
    for i in range(len(years)):
        val = 0
        if i == len(years) - 1:
            # Final year: surplus
            eq_cf = pf.get("cash_flows", {}).get("equity_cf_for_irr", [])
            if eq_cf and len(eq_cf) > len(years):
                val = eq_cf[-1]
        _c(ws, 41, 14 + i, val, F_BOLD, fmt=SAR_FMT, align=CENTER)

    # === ROW 36: Fund fees section ===
    _c(ws, 36, 2, "رسوم الصندوق والتمويل", F_HEADER, FILL_SECTION)
    _c(ws, 36, 4, "Financing & Fund Cost Assumptions", F_HEADER)

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

def _build_zoning_sheet(wb: Workbook, land: dict) -> None:
    ws = wb.create_sheet("تقرير الأنظمة")
    ws.sheet_view.rightToLeft = True
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["D"].width = 35

    _c(ws, 1, 2, "تقرير أنظمة البناء والتنظيم", Font(name=FONT_AR, size=16, bold=True, color="FFFFFF"), FILL_HEADER, align=CENTER)
    ws.merge_cells("B1:D1")

    regs = land.get("regulations", {})
    items = [
        ("رقم القطعة", land.get("parcel_number")),
        ("رقم المخطط", land.get("plan_number")),
        ("الحي", land.get("district_name")),
        ("البلدية", land.get("municipality")),
        ("مساحة الأرض (م²)", land.get("area_sqm")),
        ("نظام البناء", land.get("building_code_label")),
        ("", ""),
        ("عدد الأدوار", regs.get("max_floors")),
        ("معامل البناء (FAR)", regs.get("far")),
        ("نسبة التغطية", regs.get("coverage_ratio")),
        ("الاستخدامات المسموحة", ", ".join(regs.get("allowed_uses", []))),
        ("الارتدادات (م)", ", ".join(str(v) for v in regs.get("setback_values_m", []))),
        ("الاستخدام الرئيسي", land.get("primary_use_label")),
        ("استخدام الأرض", land.get("detailed_use_label")),
    ]
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
    notes = regs.get("notes", [])
    if notes:
        r += 1
        _c(ws, r, 2, "الملاحظات", F_HEADER)
        r += 1
        for note in notes:
            _c(ws, r, 2, note, F_SMALL, align=Alignment(wrap_text=True))
            ws.merge_cells(f"B{r}:D{r}")
            r += 1


# ---------------------------------------------------------------------------
# Sheet 3: Market Data
# ---------------------------------------------------------------------------

def _build_market_sheet(wb: Workbook, land: dict) -> None:
    ws = wb.create_sheet("بيانات السوق")
    ws.sheet_view.rightToLeft = True
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["D"].width = 25

    _c(ws, 1, 2, "بيانات البورصة العقارية (SREM)", Font(name=FONT_AR, size=16, bold=True, color="FFFFFF"), FILL_HEADER, align=CENTER)
    ws.merge_cells("B1:D1")

    mkt = land.get("market", {})
    items = [
        ("مؤشر السوق", mkt.get("srem_market_index")),
        ("التغير", mkt.get("srem_index_change")),
        ("عدد الصفقات اليومية", mkt.get("daily_total_transactions")),
        ("إجمالي القيمة اليومية (ر.س)", mkt.get("daily_total_value_sar")),
        ("متوسط السعر / م²", mkt.get("daily_avg_price_sqm")),
    ]
    r = 3
    for label, val in items:
        _c(ws, r, 2, label, F_BOLD, FILL_DATA, align=RIGHT_AL, border=BORDER_THIN)
        _c(ws, r, 4, val, F_NORMAL, fmt=SAR_FMT if isinstance(val, (int, float)) and val and val > 100 else "0.00", align=CENTER, border=BORDER_THIN)
        r += 1

    # Trending districts
    trending = mkt.get("trending_districts", [])
    if trending:
        r += 2
        _c(ws, r, 2, "الأحياء الأكثر تداولاً", F_HEADER)
        r += 1
        _c(ws, r, 2, "الحي", F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        _c(ws, r, 3, "المدينة", F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        _c(ws, r, 4, "الصفقات", F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        _c(ws, r, 5, "القيمة (ر.س)", F_BOLD, FILL_SECTION, align=CENTER, border=BORDER_THIN)
        r += 1
        for d in trending:
            _c(ws, r, 2, d.get("name"), F_NORMAL, align=CENTER, border=BORDER_THIN)
            _c(ws, r, 3, d.get("city"), F_NORMAL, align=CENTER, border=BORDER_THIN)
            _c(ws, r, 4, d.get("deals"), F_NORMAL, align=CENTER, border=BORDER_THIN)
            _c(ws, r, 5, d.get("total_sar"), F_NORMAL, fmt=SAR_FMT, align=CENTER, border=BORDER_THIN)
            r += 1

    r += 2
    _c(ws, r, 2, "المصدر: البورصة العقارية - وزارة العدل", F_SMALL)


# ---------------------------------------------------------------------------
# Sheet 4: Sensitivity
# ---------------------------------------------------------------------------

def _build_sensitivity_sheet(wb: Workbook, pf: dict) -> None:
    ws = wb.create_sheet("تحليل الحساسية")
    ws.sheet_view.rightToLeft = True

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

def _build_scenario_sheet(wb: Workbook, pf: dict, land: dict) -> None:
    ws = wb.create_sheet("مقارنة السيناريوهات")
    ws.sheet_view.rightToLeft = True
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

def generate_excel(result: dict, land_object: dict) -> bytes:
    """Generate a professional .xlsx with 5 sheets."""
    wb = Workbook()

    _build_assumptions_sheet(wb, result, land_object)
    _build_zoning_sheet(wb, land_object)
    _build_market_sheet(wb, land_object)
    _build_sensitivity_sheet(wb, result)
    _build_scenario_sheet(wb, result, land_object)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
