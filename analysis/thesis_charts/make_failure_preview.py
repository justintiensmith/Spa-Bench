from pathlib import Path

from openpyxl import load_workbook


source = Path(
    "/Users/justintiensmith/Documents/lerobot/outputs/"
    "01a0678e-4e7e-7a31-b018-7fba72ab9fe5/"
    "MSc_Thesis_Bar_Charts_Verified_with_CIs.xlsx"
)
output = Path("/tmp/Spa_Bench_Failure_Charts_Preview.xlsx")
workbook = load_workbook(source)
keep = {"Failure Analysis - Novel", "Failure Analysis - All"}
for sheet in list(workbook.worksheets):
    if sheet.title not in keep:
        workbook.remove(sheet)
workbook.save(output)
print(output)
