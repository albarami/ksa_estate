"""Excel pro-forma generator matching the Al-Hada format.

Produces a professional .xlsx with Arabic labels, live formulas,
conditional formatting, and charts.
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------

HEADER_FILL = PatternFill(start_color="1B5E20", end_color="1B5E20", fill_type="solid")
HEADER_FONT = Font(name="IBM Plex Sans Arabic", bold=True, color="FFFFFF", size=11)
SECTION_FILL = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
SECTION_FONT = Font(name="IBM Plex Sans Arabic", bold=True, size=11)
LABEL_FONT = Font(name="IBM Plex Sans Arabic", size=10)
VALUE_FONT = Font(name="IBM Plex Sans Arabic", size=10)
KPI_FONT = Font(name="IBM Plex Sans Arabic", bold=True, size=12, color="1B5E20")
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
SAR_FMT = '_(* #,##0_);_(* (#,##0);_(* "-"??_);_(@_)'
PCT_FMT = "0.0%"
PCT2_FMT = "0.00%"
RTL = Alignment(horizontal="right", vertical="center", wrap_text=True)
CENTER = Alignment(horizontal="center", vertical="center")


def _style_header(ws, row: int, cols: int) -> None:
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = THIN_BORDER


def _write_row(ws, row: int, label_ar: str, value: Any, fmt: str = SAR_FMT,
               col_label: int = 2, col_value: int = 4) -> None:
    lc = ws.cell(row=row, column=col_label, value=label_ar)
    lc.font = LABEL_FONT
    lc.alignment = RTL
    lc.border = THIN_BORDER
    vc = ws.cell(row=row, column=col_value, value=value)
    vc.font = VALUE_FONT
    vc.number_format = fmt
    vc.alignment = RTL
    vc.border = THIN_BORDER


def _section_header(ws, row: int, title: str, cols: int = 5) -> None:
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = SECTION_FILL
        cell.font = SECTION_FONT
        cell.border = THIN_BORDER
    ws.cell(row=row, column=2, value=title).alignment = RTL


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

def _build_summary_sheet(wb: Workbook, result: dict, land: dict) -> None:
    ws = wb.active
    ws.title = "الملخص التنفيذي"
    ws.sheet_view.rightToLeft = True
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 5
    ws.column_dimensions["D"].width = 25

    _style_header(ws, 1, 5)
    ws.cell(row=1, column=2, value="الملخص التنفيذي - صندوق استثمار عقاري")
    ws.merge_cells("B1:D1")

    r = 3
    fs = result.get("fund_size", {})
    kpis = result.get("kpis", {})
    rev = result.get("revenue", {})

    items = [
        ("رقم القطعة", land.get("parcel_number"), None),
        ("رقم المخطط", land.get("plan_number"), None),
        ("الحي", land.get("district_name"), None),
        ("البلدية", land.get("municipality"), None),
        ("مساحة الأرض (م²)", land.get("area_sqm"), SAR_FMT),
        ("نظام البناء", land.get("building_code_label"), None),
        ("", "", None),
        ("إجمالي حجم الصندوق", fs.get("total_fund_size"), SAR_FMT),
        ("حقوق الملكية", fs.get("equity_amount"), SAR_FMT),
        ("التمويل البنكي", fs.get("bank_loan"), SAR_FMT),
        ("إجمالي الإيرادات", rev.get("gross_revenue"), SAR_FMT),
        ("صافي الربح", kpis.get("equity_net_profit"), SAR_FMT),
        ("", "", None),
        ("معدل العائد الداخلي (IRR)", kpis.get("irr"), PCT2_FMT),
        ("العائد على حقوق الملكية", kpis.get("roe_total"), PCT_FMT),
        ("العائد السنوي", kpis.get("roe_annualized"), PCT2_FMT),
    ]
    for label, val, fmt in items:
        if label == "":
            r += 1
            continue
        _write_row(ws, r, label, val, fmt or "@")
        r += 1


def _build_assumptions_sheet(wb: Workbook, result: dict, land: dict) -> None:
    ws = wb.create_sheet("الافتراضات")
    ws.sheet_view.rightToLeft = True
    ws.column_dimensions["B"].width = 35
    ws.column_dimensions["C"].width = 5
    ws.column_dimensions["D"].width = 20
    ws.column_dimensions["E"].width = 12

    _style_header(ws, 1, 5)
    ws.cell(row=1, column=2, value="الافتراضات")

    inputs = result.get("inputs_used", {})
    r = 3
    _section_header(ws, r, "افتراضات الأرض")
    r += 1
    land_keys = [
        ("land_area_sqm", "مساحة الأرض", SAR_FMT),
        ("land_price_per_sqm", "سعر الاستحواذ بالمتر", SAR_FMT),
        ("far", "معامل البناء (FAR)", "0.0"),
        ("max_floors", "عدد الأدوار", "0"),
        ("coverage_ratio", "نسبة التغطية", PCT_FMT),
    ]
    for key, label, fmt in land_keys:
        inp = inputs.get(key, {})
        val = inp.get("value")
        src = inp.get("source", "")
        _write_row(ws, r, label, val, fmt)
        ws.cell(row=r, column=5, value=src).font = Font(size=8, italic=True, color="888888")
        r += 1

    r += 1
    _section_header(ws, r, "افتراضات التكاليف")
    r += 1
    cost_keys = [
        ("infrastructure_cost_per_sqm", "تكلفة البنية التحتية / م²", SAR_FMT),
        ("superstructure_cost_per_sqm", "تكلفة البنية العلوية / م²", SAR_FMT),
        ("developer_fee_pct", "أتعاب المطور", PCT_FMT),
        ("contingency_pct", "احتياطي", PCT_FMT),
    ]
    for key, label, fmt in cost_keys:
        inp = inputs.get(key, {})
        _write_row(ws, r, label, inp.get("value"), fmt)
        ws.cell(row=r, column=5, value=inp.get("source", "")).font = Font(size=8, italic=True, color="888888")
        r += 1

    r += 1
    _section_header(ws, r, "افتراضات المبيعات")
    r += 1
    _write_row(ws, r, "سعر البيع / م²", inputs.get("sale_price_per_sqm", {}).get("value"), SAR_FMT)
    r += 1
    _write_row(ws, r, "نسبة الكفاءة", inputs.get("efficiency_ratio", {}).get("value"), PCT_FMT)

    r += 2
    _section_header(ws, r, "افتراضات التمويل")
    r += 1
    fin_keys = [
        ("bank_ltv_pct", "نسبة التمويل البنكي", PCT_FMT),
        ("interest_rate_pct", "معدل الفائدة", PCT2_FMT),
        ("fund_period_years", "مدة الصندوق (سنوات)", "0"),
    ]
    for key, label, fmt in fin_keys:
        inp = inputs.get(key, {})
        _write_row(ws, r, label, inp.get("value"), fmt)
        r += 1


def _build_costs_sheet(wb: Workbook, result: dict) -> None:
    ws = wb.create_sheet("التكاليف")
    ws.sheet_view.rightToLeft = True
    ws.column_dimensions["B"].width = 35
    ws.column_dimensions["D"].width = 22

    _style_header(ws, 1, 5)
    ws.cell(row=1, column=2, value="تفصيل التكاليف")

    lc = result.get("land_costs", {})
    cc = result.get("construction_costs", {})
    ff = result.get("fund_fees", {})
    fin = result.get("financing", {})

    r = 3
    _section_header(ws, r, "تكاليف الأرض")
    r += 1
    for label, key in [
        ("سعر الأرض", "land_price_total"),
        ("السعي", "brokerage_fee"),
        ("ضريبة التصرفات العقارية", "transfer_tax"),
        ("ضريبة السعي", "brokerage_vat"),
        ("إجمالي تكاليف الأرض", "total_land_acquisition"),
    ]:
        _write_row(ws, r, label, lc.get(key))
        if "إجمالي" in label:
            ws.cell(row=r, column=2).font = SECTION_FONT
        r += 1

    r += 1
    _section_header(ws, r, "التكاليف المباشرة")
    r += 1
    for label, key in [
        ("المساحة الإجمالية (GBA)", "gba_sqm"),
        ("البنية التحتية", "infrastructure_cost"),
        ("البنية العلوية", "superstructure_cost"),
        ("المواقف", "parking_cost"),
        ("إجمالي التكاليف المباشرة", "total_direct_cost"),
    ]:
        _write_row(ws, r, label, cc.get(key))
        r += 1

    r += 1
    _section_header(ws, r, "التكاليف غير المباشرة")
    r += 1
    for label, key in [
        ("أتعاب المطور", "developer_fee"),
        ("تكاليف أخرى", "other_indirect"),
        ("احتياطي", "contingency"),
        ("إجمالي التكاليف غير المباشرة", "total_indirect_cost"),
    ]:
        _write_row(ws, r, label, cc.get(key))
        r += 1

    r += 1
    _section_header(ws, r, "رسوم الصندوق والتمويل")
    r += 1
    for label, key in [
        ("فوائد التمويل", None),
        ("رسوم إدارة الصندوق", "management_fee"),
        ("رسوم أمين الحفظ", "custodian_fee"),
        ("مجلس الإدارة", "board_fee"),
        ("رسوم هيكلة", "structuring_fee"),
        ("إجمالي رسوم الصندوق", "total_fund_fees"),
    ]:
        val = fin.get("total_interest") if key is None else ff.get(key)
        _write_row(ws, r, label, val)
        r += 1


def _build_cashflow_sheet(wb: Workbook, result: dict) -> None:
    ws = wb.create_sheet("التدفقات النقدية")
    ws.sheet_view.rightToLeft = True
    ws.column_dimensions["B"].width = 30

    cf = result.get("cash_flows", {})
    years = cf.get("years", [])
    n = len(years)

    for c in range(3, 3 + n):
        ws.column_dimensions[get_column_letter(c)].width = 18

    _style_header(ws, 1, 2 + n)
    ws.cell(row=1, column=2, value="التدفقات النقدية")

    # Year headers
    r = 3
    ws.cell(row=r, column=2, value="السنة").font = SECTION_FONT
    for i, yr in enumerate(years):
        cell = ws.cell(row=r, column=3 + i, value=f"Y{yr}")
        cell.font = SECTION_FONT
        cell.alignment = CENTER

    # Data rows
    rows_data = [
        ("المبيعات", cf.get("inflows_sales", [])),
        ("تكاليف الأرض", cf.get("outflows_land", [])),
        ("التكاليف المباشرة", cf.get("outflows_direct", [])),
        ("التكاليف غير المباشرة", cf.get("outflows_indirect", [])),
        ("الفوائد", cf.get("outflows_interest", [])),
        ("الرسوم", cf.get("outflows_fees", [])),
        ("إجمالي التدفقات الخارجة", cf.get("outflows_total", [])),
        ("صافي التدفقات النقدية", cf.get("net_cash_flow", [])),
        ("التدفقات التراكمية", cf.get("cumulative", [])),
    ]

    r = 5
    for label, vals in rows_data:
        ws.cell(row=r, column=2, value=label).font = LABEL_FONT
        ws.cell(row=r, column=2).alignment = RTL
        ws.cell(row=r, column=2).border = THIN_BORDER
        for i, v in enumerate(vals):
            cell = ws.cell(row=r, column=3 + i, value=v)
            cell.number_format = SAR_FMT
            cell.border = THIN_BORDER
            cell.alignment = RTL
        if "إجمالي" in label or "صافي" in label or "تراكمية" in label:
            for c in range(2, 3 + n):
                ws.cell(row=r, column=c).font = SECTION_FONT
        r += 1

    # Cash flow bar chart
    if n > 0:
        chart = BarChart()
        chart.title = "التدفقات النقدية"
        chart.type = "col"
        chart.y_axis.title = "SAR"
        net_row = 5 + len(rows_data) - 2  # net_cash_flow row
        data = Reference(ws, min_col=3, max_col=2 + n, min_row=net_row, max_row=net_row)
        cats = Reference(ws, min_col=3, max_col=2 + n, min_row=3, max_row=3)
        chart.add_data(data, from_rows=True)
        chart.set_categories(cats)
        chart.width = 20
        chart.height = 12
        ws.add_chart(chart, f"B{r + 2}")


def _build_sensitivity_sheet(wb: Workbook, result: dict) -> None:
    ws = wb.create_sheet("تحليل الحساسية")
    ws.sheet_view.rightToLeft = True

    sens = result.get("sensitivity")
    if not sens:
        ws.cell(row=2, column=2, value="لا تتوفر بيانات تحليل الحساسية")
        return

    sale_range = sens.get("sale_price_range", [])
    cost_range = sens.get("construction_cost_range", [])
    matrix = sens.get("irr_matrix", [])

    ws.column_dimensions["B"].width = 18
    for i in range(len(cost_range)):
        ws.column_dimensions[get_column_letter(3 + i)].width = 14

    _style_header(ws, 1, 2 + len(cost_range))
    ws.cell(row=1, column=2, value="تحليل الحساسية - IRR")

    # Headers
    ws.cell(row=3, column=2, value="سعر البيع \\ التكلفة").font = SECTION_FONT
    for i, c in enumerate(cost_range):
        cell = ws.cell(row=3, column=3 + i, value=c)
        cell.font = SECTION_FONT
        cell.number_format = "#,##0"
        cell.alignment = CENTER

    # Matrix
    for ri, sp in enumerate(sale_range):
        r = 4 + ri
        cell = ws.cell(row=r, column=2, value=sp)
        cell.number_format = "#,##0"
        cell.font = LABEL_FONT
        for ci, irr_val in enumerate(matrix[ri]):
            cell = ws.cell(row=r, column=3 + ci)
            if irr_val is not None:
                cell.value = irr_val
                cell.number_format = PCT2_FMT
                # Color: green if positive, red if negative
                if irr_val >= 0.10:
                    cell.fill = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")
                elif irr_val >= 0:
                    cell.fill = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")
                else:
                    cell.fill = PatternFill(start_color="FFCDD2", end_color="FFCDD2", fill_type="solid")
            else:
                cell.value = "N/A"
            cell.border = THIN_BORDER
            cell.alignment = CENTER


def _build_fund_structure_sheet(wb: Workbook, result: dict) -> None:
    ws = wb.create_sheet("هيكل الصندوق")
    ws.sheet_view.rightToLeft = True
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 12

    _style_header(ws, 1, 5)
    ws.cell(row=1, column=2, value="هيكل رأس المال")

    fs = result.get("fund_size", {})
    r = 3
    items = [
        ("حقوق الملكية (Equity)", fs.get("equity_amount", 0), fs.get("equity_pct", 0)),
        ("التمويل البنكي (Debt)", fs.get("bank_loan", 0), fs.get("debt_pct", 0)),
        ("إجمالي رأس المال", fs.get("total_fund_size", 0), 1.0),
    ]
    ws.cell(row=r, column=2, value="المكون").font = SECTION_FONT
    ws.cell(row=r, column=4, value="المبلغ (ر.س)").font = SECTION_FONT
    ws.cell(row=r, column=5, value="النسبة").font = SECTION_FONT
    r += 1
    data_start = r
    for label, amount, pct in items:
        ws.cell(row=r, column=2, value=label).font = LABEL_FONT
        ws.cell(row=r, column=4, value=amount).number_format = SAR_FMT
        ws.cell(row=r, column=5, value=pct).number_format = PCT_FMT
        for c in range(2, 6):
            ws.cell(row=r, column=c).border = THIN_BORDER
        r += 1

    # Pie chart
    pie = PieChart()
    pie.title = "هيكل رأس المال"
    labels = Reference(ws, min_col=2, min_row=data_start, max_row=data_start + 1)
    data = Reference(ws, min_col=4, min_row=data_start, max_row=data_start + 1)
    pie.add_data(data)
    pie.set_categories(labels)
    pie.width = 18
    pie.height = 14
    ws.add_chart(pie, f"B{r + 2}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_excel(
    result: dict,
    land_object: dict,
) -> bytes:
    """Generate a professional .xlsx pro-forma report.

    Args:
        result: ProFormaResult from computation_engine.
        land_object: Land Object from data_fetch.

    Returns:
        bytes: .xlsx file content.
    """
    wb = Workbook()

    _build_summary_sheet(wb, result, land_object)
    _build_assumptions_sheet(wb, result, land_object)
    _build_costs_sheet(wb, result)
    _build_cashflow_sheet(wb, result)
    _build_sensitivity_sheet(wb, result)
    _build_fund_structure_sheet(wb, result)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
