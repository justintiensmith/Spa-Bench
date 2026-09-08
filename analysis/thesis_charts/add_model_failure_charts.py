from __future__ import annotations

import json
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.data_source import NumData, NumDataSource, NumRef, NumVal
from openpyxl.chart.error_bar import ErrorBars
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils.cell import range_boundaries


WORK_DIR = Path("/Users/justintiensmith/Documents/lerobot/output/thesis_bar_charts_audit")
OUTPUT_DIR = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5"
)
SOURCE = OUTPUT_DIR / "MSc_Thesis_Bar_Charts_Verified_with_CIs.xlsx"
OUTPUT = OUTPUT_DIR / "MSc_Thesis_Bar_Charts_with_Model_Failure_Profiles.xlsx"
DATA = json.loads((WORK_DIR / "model_failure_chart_data.json").read_text(encoding="utf-8"))

CHART_SHEET = "Failure by Model - All"
DATA_SHEET = "Failure by Model - Data"
BLUE = "4F81BD"
HEADER_BLUE = "1F4E78"
TEXT = "1F1F1F"
SUBTLE = "595959"
DISPLAY_NAMES = {
    "VLA-0": "VLA-0",
    "GR00T Full Fine-Tune": "GR00T Full Fine-Tune",
    "GR00T Frozen LLM": "GR00T Frozen LLM",
    "Pi0.5": "Pi0.5",
    "MolmoAct2": "MolmoAct2",
}


def quote_sheet(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def set_row(ws, row: int, values: list[object]) -> None:
    for column, value in enumerate(values, start=1):
        ws.cell(row=row, column=column, value=value)


def custom_error_bars(wb, sheet_name: str, minus_range: str, plus_range: str) -> ErrorBars:
    def source(address: str) -> NumDataSource:
        min_col, min_row, max_col, max_row = range_boundaries(address.replace("$", ""))
        values = [
            wb[sheet_name].cell(row=row, column=column).value
            for row in range(min_row, max_row + 1)
            for column in range(min_col, max_col + 1)
        ]
        cache = NumData(
            formatCode="0.0%",
            ptCount=len(values),
            pt=[NumVal(idx=index, v=float(value)) for index, value in enumerate(values)],
        )
        return NumDataSource(
            numRef=NumRef(f=f"{quote_sheet(sheet_name)}!{address}", numCache=cache)
        )

    bars = ErrorBars(
        errDir="x",
        errBarType="both",
        errValType="cust",
        noEndCap=False,
        minus=source(minus_range),
        plus=source(plus_range),
    )
    bars.spPr = GraphicalProperties()
    bars.spPr.line.solidFill = "000000"
    bars.spPr.line.width = 12700
    return bars


def chart_signature(chart) -> dict:
    series = []
    for item in chart.ser:
        value_formula = item.val.numRef.f if item.val and item.val.numRef else None
        category_formula = None
        if item.cat:
            if item.cat.strRef:
                category_formula = item.cat.strRef.f
            elif item.cat.numRef:
                category_formula = item.cat.numRef.f
            elif item.cat.multiLvlStrRef:
                category_formula = item.cat.multiLvlStrRef.f
        error_signature = None
        if item.errBars:
            error_signature = (
                item.errBars.errDir,
                item.errBars.errBarType,
                item.errBars.errValType,
                item.errBars.minus.numRef.f if item.errBars.minus and item.errBars.minus.numRef else None,
                item.errBars.plus.numRef.f if item.errBars.plus and item.errBars.plus.numRef else None,
            )
        series.append((value_formula, category_formula, error_signature))
    return {
        "class": type(chart).__name__,
        "type": getattr(chart, "type", None),
        "grouping": getattr(chart, "grouping", None),
        "width": chart.width,
        "height": chart.height,
        "series": series,
    }


def worksheet_signature(ws) -> dict:
    cells = [
        (row, column, cell.value, cell.data_type, cell.style_id, cell.number_format)
        for (row, column), cell in sorted(ws._cells.items())
    ]
    return {
        "cells": cells,
        "charts": [chart_signature(chart) for chart in ws._charts],
        "sheet_format": (ws.sheet_format.defaultColWidth, ws.sheet_format.defaultRowHeight),
        "freeze": str(ws.freeze_panes),
        "gridlines": ws.sheet_view.showGridLines,
    }


wb = load_workbook(SOURCE)
original_sheet_names = list(wb.sheetnames)
original_signatures = {name: worksheet_signature(wb[name]) for name in original_sheet_names}

for sheet_name in (CHART_SHEET, DATA_SHEET):
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]

chart_ws = wb.create_sheet(CHART_SHEET)
chart_ws.sheet_view.showGridLines = False
chart_ws["A1"] = "Failure-mode profiles by model"
chart_ws["A2"] = (
    "All tasks and evaluation conditions. Shares are conditional on each model's failed rollouts; "
    "they are not failure rates over all attempts."
)
chart_ws["A3"] = (
    "Bars show the share of each model's failures assigned to each primary failure mode; "
    "whiskers show two-sided Wilson 95% confidence intervals."
)
chart_ws["A4"] = "Source: Spa_Bench_All_Failure_Audit.xlsx, All Classified Failures."
chart_ws["A1"].font = Font(name="Arial", size=16, bold=True, color=TEXT)
for row in (2, 3, 4):
    chart_ws.cell(row, 1).font = Font(name="Arial", size=10, italic=True, color=SUBTLE)

data_ws = wb.create_sheet(DATA_SHEET)
data_ws.sheet_view.showGridLines = False
data_ws["A1"] = "Failure-mode profile data"
data_ws["A2"] = (
    "All tasks and evaluation conditions. Each share uses that model's failed rollouts as its denominator."
)
data_ws["A3"] = "Source: Spa_Bench_All_Failure_Audit.xlsx, All Classified Failures."
data_ws["A1"].font = Font(name="Arial", size=16, bold=True, color=TEXT)
for row in (2, 3):
    data_ws.cell(row, 1).font = Font(name="Arial", size=10, italic=True, color=SUBTLE)

header_fill = PatternFill("solid", fgColor=HEADER_BLUE)
thin = Side(style="thin", color="D9E2F3")
headers = [
    "Model",
    "Failure mode",
    "Count",
    "Model failures",
    "Share",
    "Wilson 95% lower",
    "Wilson 95% upper",
    "Lower error",
    "Upper error",
]
set_row(data_ws, 5, headers)
for cell in data_ws[5]:
    cell.fill = header_fill
    cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
data_ws.row_dimensions[5].height = 30
data_ws.column_dimensions["A"].width = 25
data_ws.column_dimensions["B"].width = 44
data_ws.column_dimensions["C"].width = 11
data_ws.column_dimensions["D"].width = 15
for column in ("E", "F", "G", "H", "I"):
    data_ws.column_dimensions[column].width = 18

chart_starts = [6, 34, 62, 90, 118]
expected_chart_data = []
next_data_row = 6
for model, chart_start in zip(DATA["model_order"], chart_starts):
    total = int(DATA["model_totals"][model])
    model_rows = [row for row in DATA["rows"] if row["Model"] == model]
    order = {mode: index for index, mode in enumerate(DATA["failure_mode_order"])}
    model_rows.sort(key=lambda row: order[row["Failure Mode"]])
    if len(model_rows) != len(DATA["failure_mode_order"]):
        raise AssertionError(f"Incomplete failure-mode data for {model}.")

    first_data_row = next_data_row
    last_data_row = first_data_row + len(model_rows) - 1
    for row_number, datum in enumerate(model_rows, start=first_data_row):
        set_row(
            data_ws,
            row_number,
            [
                DISPLAY_NAMES[model],
                datum["Failure Mode"],
                datum["Count"],
                datum["Model Failures"],
                datum["Share"],
                datum["CI Lower"],
                datum["CI Upper"],
                datum["Lower Error"],
                datum["Upper Error"],
            ],
        )
        for cell in data_ws[row_number][:9]:
            cell.font = Font(name="Arial", size=10, color=TEXT)
            cell.border = Border(bottom=thin)
        data_ws.cell(row_number, 2).alignment = Alignment(vertical="center", wrap_text=True)
        data_ws.cell(row_number, 3).number_format = "#,##0"
        data_ws.cell(row_number, 4).number_format = "#,##0"
        for column in range(5, 10):
            data_ws.cell(row_number, column).number_format = "0.0%"

    chart = BarChart()
    chart.type = "bar"
    chart.grouping = "clustered"
    chart.style = 10
    chart.title = f"{DISPLAY_NAMES[model]} failure profile (n={total})"
    chart.legend = None
    chart.width = 25
    chart.height = 10
    chart.x_axis.scaling.orientation = "maxMin"
    chart.x_axis.axPos = "l"
    chart.y_axis.title = "Share of model's failed rollouts"
    chart.y_axis.scaling.min = 0
    chart.y_axis.scaling.max = 0.75
    chart.y_axis.numFmt = "0%"
    chart.y_axis.majorUnit = 0.15
    chart.y_axis.axPos = "b"
    chart.y_axis.tickLblPos = "low"
    chart.overlap = 0
    chart.gapWidth = 55
    data = Reference(data_ws, min_col=5, min_row=5, max_row=last_data_row)
    categories = Reference(data_ws, min_col=2, min_row=first_data_row, max_row=last_data_row)
    # Restrict the value series to this model's nine rows while preserving the common header.
    data = Reference(data_ws, min_col=5, min_row=first_data_row - 1, max_row=last_data_row)
    data_ws.cell(first_data_row - 1, 5, "Share")
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    chart.ser[0].graphicalProperties.solidFill = BLUE
    chart.ser[0].graphicalProperties.line.solidFill = BLUE
    chart.ser[0].errBars = custom_error_bars(
        wb,
        DATA_SHEET,
        f"$H${first_data_row}:$H${last_data_row}",
        f"$I${first_data_row}:$I${last_data_row}",
    )
    chart.dLbls = DataLabelList(
        showVal=True,
        showCatName=False,
        showSerName=False,
        showLegendKey=False,
        showPercent=False,
        showBubbleSize=False,
        showLeaderLines=False,
        numFmt="0%",
        dLblPos="outEnd",
    )
    chart_ws.add_chart(chart, f"A{chart_start}")
    expected_chart_data.append(
        {
            "model": model,
            "total": total,
            "first_data_row": first_data_row,
            "last_data_row": last_data_row,
        }
    )
    next_data_row = last_data_row + 2

data_ws.freeze_panes = "A6"
data_ws.auto_filter.ref = f"A5:I{next_data_row - 2}"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
wb.calculation.fullCalcOnLoad = True
wb.calculation.forceFullCalc = True
wb.calculation.calcMode = "auto"
wb.save(OUTPUT)


# Re-open and verify all pre-existing sheets are logically unchanged.
verified = load_workbook(OUTPUT, data_only=False)
for name in original_sheet_names:
    if original_signatures[name] != worksheet_signature(verified[name]):
        raise AssertionError(f"Existing sheet changed unexpectedly: {name}")

new_chart_ws = verified[CHART_SHEET]
new_data_ws = verified[DATA_SHEET]
if len(new_chart_ws._charts) != 5:
    raise AssertionError(f"Expected five charts; found {len(new_chart_ws._charts)}")
if sum(int(new_data_ws.cell(row=item["first_data_row"] + offset, column=3).value) for item in expected_chart_data for offset in range(9)) != DATA["total_failures"]:
    raise AssertionError("Failure counts do not reconcile to the source total.")

for chart, expected in zip(new_chart_ws._charts, expected_chart_data):
    if chart.type != "bar":
        raise AssertionError("Expected horizontal bar charts.")
    if chart.y_axis.scaling.min != 0 or chart.y_axis.scaling.max != 0.75:
        raise AssertionError("All charts must use the same 0%-75% scale.")
    if len(chart.ser) != 1 or chart.ser[0].errBars is None:
        raise AssertionError("Each chart must have one series with confidence intervals.")
    if chart.ser[0].errBars.errValType != "cust" or chart.ser[0].errBars.errDir != "x":
        raise AssertionError("Each chart must use custom horizontal error bars.")
    if chart.ser[0].graphicalProperties.solidFill.srgbClr != BLUE:
        raise AssertionError("Chart bar color does not match Pi0.5 Robustness blue.")

verification = {
    "source": str(SOURCE),
    "output": str(OUTPUT),
    "new_sheets": [CHART_SHEET, DATA_SHEET],
    "chart_count": len(new_chart_ws._charts),
    "total_failures": DATA["total_failures"],
    "model_totals": DATA["model_totals"],
    "existing_sheets_unchanged": True,
    "chart_scale": [0, 0.75],
    "bar_color": f"#{BLUE}",
    "charts": expected_chart_data,
}
(WORK_DIR / "model_failure_chart_verification.json").write_text(
    json.dumps(verification, indent=2), encoding="utf-8"
)
print(json.dumps(verification, indent=2))
