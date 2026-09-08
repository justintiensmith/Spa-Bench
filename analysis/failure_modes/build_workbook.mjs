import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const here = path.dirname(new URL(import.meta.url).pathname);
const payload = JSON.parse(await fs.readFile(path.join(here, "analysis_payload_all_audited.json"), "utf8"));
const outputDir = "/Users/justintiensmith/Documents/lerobot/outputs/01a0678e-4e7e-7a31-b018-7fba72ab9fe5";
const outputPath = path.join(outputDir, "Spa_Bench_All_Failure_Audit.xlsx");
const renderDir = path.join(here, "workbook_renders_all_failure_audit");

const workbook = Workbook.create();
const readme = workbook.worksheets.add("Read Me");
const gallery = workbook.worksheets.add("Matrix Gallery");
const cellMap = workbook.worksheets.add("Missing Cell Map");
const summary = workbook.worksheets.add("Failure Summary");
const byTask = workbook.worksheets.add("Failure by Task");
const byModel = workbook.worksheets.add("Failure by Model");
const allSummary = workbook.worksheets.add("All Failure Summary");
const byCondition = workbook.worksheets.add("Failure by Condition");
const reviewQueue = workbook.worksheets.add("Review Queue");
const primarySheet = workbook.worksheets.add("Primary Failures");
const allSheet = workbook.worksheets.add("All Classified Failures");
const names = workbook.worksheets.add("Task Names");
const methods = workbook.worksheets.add("Methods");

const navy = "#17365D";
const blue = "#2F75B5";
const paleBlue = "#D9EAF7";
const green = "#B8DDAA";
const salmon = "#E6B0A5";
const gray = "#E7E7E7";
const paleGray = "#F3F5F7";
const white = "#FFFFFF";
const border = "#B8C2CC";
const fontFamily = "Arial";

function styleTitle(sheet, rangeAddress) {
  const range = sheet.getRange(rangeAddress);
  range.format = {
    fill: navy,
    font: { name: fontFamily, size: 16, bold: true, color: white },
    verticalAlignment: "center",
  };
  range.format.rowHeight = 28;
}

function styleSection(sheet, rangeAddress) {
  const range = sheet.getRange(rangeAddress);
  range.format = {
    fill: paleBlue,
    font: { name: fontFamily, size: 11, bold: true, color: navy },
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: border },
  };
}

function styleHeader(sheet, rangeAddress) {
  const range = sheet.getRange(rangeAddress);
  range.format = {
    fill: blue,
    font: { name: fontFamily, size: 10, bold: true, color: white },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: border },
  };
}

function styleBody(sheet, rangeAddress) {
  const range = sheet.getRange(rangeAddress);
  range.format = {
    font: { name: fontFamily, size: 9, color: "#1F2933" },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D9E1E8" },
  };
}

function writeTable(sheet, startRow, startCol, headers, rows, tableName) {
  const matrix = [headers, ...rows];
  const range = sheet.getRangeByIndexes(startRow, startCol, matrix.length, headers.length);
  range.values = matrix;
  styleHeader(sheet, sheet.getRangeByIndexes(startRow, startCol, 1, headers.length).getAddress());
  if (rows.length) {
    styleBody(sheet, sheet.getRangeByIndexes(startRow + 1, startCol, rows.length, headers.length).getAddress());
  }
  const table = sheet.tables.add(range.getAddress(), true, tableName);
  table.style = "TableStyleMedium2";
  table.showBandedColumns = false;
  table.showFilterButton = true;
  return range;
}

function safe(value) {
  if (value === null || value === undefined) return "";
  return value;
}

function columnLetter(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    const rem = (value - 1) % 26;
    result = String.fromCharCode(65 + rem) + result;
    value = Math.floor((value - 1) / 26);
  }
  return result;
}

// Read Me
readme.showGridLines = false;
readme.mergeCells("A1:H1");
readme.getRange("A1").values = [["Spa-Bench Manifest and All-Failure Audit"]];
styleTitle(readme, "A1:H1");
readme.getRange("A3:B10").values = [
  ["Purpose", "Auditable source data for the missing-cell design and qualitative review of every failed rollout."],
  ["Training manifest", payload.source_manifest],
  ["Evaluation workbook", payload.source_evaluations],
  ["All-failure audit", `${payload.scope.all_failures} failed rollouts across all models and evaluation conditions`],
  ["Primary-paper subset", `${payload.scope.condition}; ${payload.scope.included_models}`],
  ["Rows needing confirmation", `${payload.scope.review_queue} (${payload.scope.missing_observations} missing notes; ${payload.scope.ambiguous_nonblank} ambiguous nonblank notes)`],
  ["Unit of analysis", payload.scope.review_unit],
  ["Important caveat", payload.scope.caveat],
];
styleBody(readme, "A3:B10");
readme.getRange("A3:A10").format = { fill: paleGray, font: { name: fontFamily, bold: true, color: navy }, wrapText: true };
readme.mergeCells("A11:F11");
readme.getRange("A11").values = [["Headline findings"]];
styleSection(readme, "A11:F11");
readme.getRange("A12:B20").values = [
  ["All failed rollouts audited", payload.scope.all_failures],
  ["Failed novel rollouts classified", null],
  ["Wrong-target failures", null],
  ["Wrong-target share", null],
  ["No-action failures", null],
  ["No-action share", null],
  ["Unnecessary interventions (all conditions)", payload.scope.unnecessary_interventions],
  ["Release / retention failures", null],
  ["Rows in Review Queue", payload.scope.review_queue],
];
readme.getRange("A12:B20").format = { font: { name: fontFamily, size: 11 }, borders: { preset: "all", style: "thin", color: border } };
readme.getRange("A12:A20").format.fill = paleGray;
readme.getRange("B15").format.numberFormat = "0.0%";
readme.getRange("B17").format.numberFormat = "0.0%";
readme.getRange("A22:H25").merge();
readme.getRange("A22").values = [["Interpretation: 'Unnecessary intervention' is reserved for failed controls whose correct behavior was to leave the scene unchanged. This prevents task-directed motion in no-movement trials from being conflated with wrong-target selection or control drift. The Review Queue contains the only rows that still require rollout inspection or annotation confirmation."]];
readme.getRange("A22:H25").format = { fill: "#FFF2CC", font: { name: fontFamily, size: 10, color: "#5B4300" }, wrapText: true, verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: "#D6B656" } };
readme.getRange("A:A").format.columnWidth = 25;
readme.getRange("B:B").format.columnWidth = 78;
readme.getRange("C:H").format.columnWidth = 14;
readme.freezePanes.freezeRows(1);

// Matrix gallery
gallery.showGridLines = false;
gallery.mergeCells("A1:L1");
gallery.getRange("A1").values = [["Spa-Bench Missing-Cell Matrices"]];
styleTitle(gallery, "A1:L1");
gallery.mergeCells("A2:L2");
gallery.getRange("A2").values = [["Green = explicitly observed binding; salmon = withheld binding; gray = absent or not applicable."]];
gallery.getRange("A2:L2").format = { font: { name: fontFamily, size: 10, italic: true, color: "#4A5568" } };

function drawMatrix(sheet, matrix, startRow, startCol) {
  const rows = matrix.rows;
  const cols = matrix.columns.map((value) => value.replaceAll("\n", " "));
  const title = matrix.context ? `${matrix.task} — ${matrix.context}` : matrix.task;
  const width = cols.length + 1;
  sheet.mergeCells(sheet.getRangeByIndexes(startRow, startCol, 1, width).getAddress());
  const titleRange = sheet.getRangeByIndexes(startRow, startCol, 1, width);
  titleRange.values = [[title]];
  styleSection(sheet, titleRange.getAddress());
  const headers = ["Concept / argument", ...cols];
  const headerRange = sheet.getRangeByIndexes(startRow + 1, startCol, 1, width);
  headerRange.values = [headers];
  styleHeader(sheet, headerRange.getAddress());
  const bodyRows = rows.map((rowName, index) => [rowName, ...matrix.values[index]]);
  const bodyRange = sheet.getRangeByIndexes(startRow + 2, startCol, bodyRows.length, width);
  bodyRange.values = bodyRows;
  styleBody(sheet, bodyRange.getAddress());
  sheet.getRangeByIndexes(startRow + 2, startCol, bodyRows.length, 1).format = { fill: paleGray, font: { name: fontFamily, size: 9, bold: true }, verticalAlignment: "center", borders: { preset: "all", style: "thin", color: border } };
  for (let r = 0; r < rows.length; r += 1) {
    for (let c = 0; c < cols.length; c += 1) {
      const status = matrix.values[r][c];
      const cell = sheet.getCell(startRow + 2 + r, startCol + 1 + c);
      cell.format.fill = status === "Observed" ? green : status === "Withheld" ? salmon : gray;
      cell.format.verticalAlignment = "center";
      cell.format.horizontalAlignment = "center";
    }
  }
  sheet.getRangeByIndexes(startRow + 1, startCol, rows.length + 1, width).format.rowHeight = 32;
}

const matrixByKey = new Map(payload.matrices.map((m) => [`${m.task}|${m.context}`, m]));
drawMatrix(gallery, matrixByKey.get("Physical State|"), 3, 0);
drawMatrix(gallery, matrixByKey.get("Ordinal Position|2-object sequences"), 3, 6);
drawMatrix(gallery, matrixByKey.get("Relative Size|"), 11, 0);
drawMatrix(gallery, matrixByKey.get("Ordinal Position|3-object sequences"), 10, 6);
drawMatrix(gallery, matrixByKey.get("Referential Description|"), 17, 0);
drawMatrix(gallery, matrixByKey.get("Ordinal Position|4-object sequences"), 17, 6);
drawMatrix(gallery, matrixByKey.get("Counting|"), 24, 0);
drawMatrix(gallery, matrixByKey.get("Relational Placement|"), 32, 0);
gallery.getRange("A:L").format.columnWidth = 17;
gallery.getRange("A:A").format.columnWidth = 20;
gallery.getRange("G:G").format.columnWidth = 20;
gallery.freezePanes.freezeRows(2);

// Long-form missing-cell map
cellMap.showGridLines = false;
cellMap.mergeCells("A1:E1");
cellMap.getRange("A1").values = [["Missing-Cell Map (Long Form)"]];
styleTitle(cellMap, "A1:E1");
const cellRows = payload.matrix_cells.map((r) => [r.Task, r.Context, r.Concept, r.Argument, r.Status]);
writeTable(cellMap, 2, 0, ["Task", "Context", "Concept", "Argument", "Status"], cellRows, "MissingCellMapTable");
for (let i = 0; i < cellRows.length; i += 1) {
  const cell = cellMap.getCell(3 + i, 4);
  const status = cellRows[i][4];
  cell.format.fill = status === "Observed" ? green : status === "Withheld" ? salmon : gray;
}
cellMap.getRange("A:A").format.columnWidth = 24;
cellMap.getRange("B:B").format.columnWidth = 22;
cellMap.getRange("C:C").format.columnWidth = 18;
cellMap.getRange("D:D").format.columnWidth = 34;
cellMap.getRange("E:E").format.columnWidth = 14;
cellMap.freezePanes.freezeRows(3);

// Primary failures data
const failureHeaders = [
  "Model",
  "Task",
  "Episode",
  "Condition",
  "Comparison / Subtype",
  "Prompt",
  "Expected Target / Action",
  "Observation",
  "Primary Failure Mode",
  "Secondary Flags",
  "Classification Confidence",
  "Classification Basis",
  "Needs Manual Review",
];
function failureRow(r) {
  return [
    safe(r.Model), safe(r["Canonical Task"]), safe(r.Episode), safe(r.Condition),
    safe(r["Comparison / Subtype"]), safe(r.Prompt), safe(r["Expected Target / Action"]),
    safe(r.Observation ?? r.Observations), safe(r["Primary Failure Mode"]), safe(r["Secondary Flags"]),
    safe(r["Classification Confidence"]), safe(r["Classification Basis"]), safe(r["Needs Manual Review"]),
  ];
}

primarySheet.showGridLines = false;
primarySheet.mergeCells("A1:M1");
primarySheet.getRange("A1").values = [["Primary Novel-Spatial-Grounding Failures"]];
styleTitle(primarySheet, "A1:M1");
primarySheet.mergeCells("A2:M2");
primarySheet.getRange("A2").values = [["One mutually exclusive primary failure mode per failed rollout. Secondary flags preserve additional information from the qualitative annotation."]];
primarySheet.getRange("A2:M2").format = { fill: "#FFF2CC", font: { name: fontFamily, size: 9, color: "#5B4300" }, wrapText: true };
writeTable(primarySheet, 2, 0, failureHeaders, payload.primary_failures.map(failureRow), "PrimaryFailuresTable");
primarySheet.getRange("A:A").format.columnWidth = 20;
primarySheet.getRange("B:B").format.columnWidth = 24;
primarySheet.getRange("C:C").format.columnWidth = 9;
primarySheet.getRange("D:E").format.columnWidth = 28;
primarySheet.getRange("F:H").format.columnWidth = 44;
primarySheet.getRange("I:J").format.columnWidth = 32;
primarySheet.getRange("K:K").format.columnWidth = 18;
primarySheet.getRange("L:L").format.columnWidth = 42;
primarySheet.getRange("M:M").format.columnWidth = 18;
primarySheet.freezePanes.freezeRows(3);
primarySheet.freezePanes.freezeColumns(2);

// All classified failures
allSheet.showGridLines = false;
allSheet.mergeCells("A1:M1");
allSheet.getRange("A1").values = [["All Failed Rollouts with Qualitative Classifications"]];
styleTitle(allSheet, "A1:M1");
allSheet.mergeCells("A2:M2");
allSheet.getRange("A2").values = [["Includes every failure across all model sheets and evaluation conditions. The main paper analysis uses the narrower Primary Failures sheet."]];
allSheet.getRange("A2:M2").format = { fill: "#FFF2CC", font: { name: fontFamily, size: 9, color: "#5B4300" }, wrapText: true };
writeTable(allSheet, 2, 0, failureHeaders, payload.all_failures.map(failureRow), "AllFailuresTable");
allSheet.getRange("A:A").format.columnWidth = 20;
allSheet.getRange("B:B").format.columnWidth = 24;
allSheet.getRange("C:C").format.columnWidth = 9;
allSheet.getRange("D:E").format.columnWidth = 28;
allSheet.getRange("F:H").format.columnWidth = 44;
allSheet.getRange("I:J").format.columnWidth = 32;
allSheet.getRange("K:K").format.columnWidth = 18;
allSheet.getRange("L:L").format.columnWidth = 42;
allSheet.getRange("M:M").format.columnWidth = 18;
allSheet.freezePanes.freezeRows(3);
allSheet.freezePanes.freezeColumns(2);

// Overall failure summary with formula-driven counts and Wilson intervals
summary.showGridLines = false;
summary.mergeCells("A1:Q1");
summary.getRange("A1").values = [["Failure-Mode Summary: Novel Spatial Grounding"]];
styleTitle(summary, "A1:Q1");
summary.mergeCells("A2:Q2");
summary.getRange("A2").values = [["Scope: three fully evaluated models pooled; percentages are conditional on rollout failure, not on all attempted rollouts."]];
summary.getRange("A2:Q2").format = { fill: "#FFF2CC", font: { name: fontFamily, size: 9, color: "#5B4300" }, wrapText: true };
summary.getRange("A4:F4").values = [["Failure Mode", "Count", "Share of Failures", "Wilson 95% Lower", "Wilson 95% Upper", "Interpretation"]];
styleHeader(summary, "A4:F4");
const interpretation = {
  "Wrong target": "The policy selected or attempted an object other than the spatially specified target.",
  "No action": "No task-directed motion was observed.",
  "Correct target, incorrect spatial outcome": "The correct object was used, but the requested relation or final count was not achieved.",
  "Grasp failure": "The intended target was approached but not successfully grasped.",
  "Premature release or dropped object": "The object was dropped or released before task completion.",
  "Release/retention failure": "The intended object was transported but remained in the gripper or could not be set down at the destination.",
  "Control drift or instability": "Uncommanded, oscillatory, or progressively displaced motion prevented or destabilized task completion.",
  "Timeout or incomplete execution": "The policy began appropriately but did not complete within the rollout window.",
  "Unnecessary intervention": "The policy initiated task-directed motion or changed the scene when the correct behavior was to leave it unchanged.",
  "Other execution failure": "A non-spatial execution or recovery problem prevented success.",
  "Unannotated or unclear": "The available note did not support a unique primary classification.",
};
const overallRows = payload.mode_order.map((mode) => [mode, null, null, null, null, interpretation[mode]]);
const summaryFirstRow = 5;
const summaryLastRow = summaryFirstRow + payload.mode_order.length - 1;
const summaryTotalRow = summaryLastRow + 2;
const primaryDataLastRow = 3 + payload.scope.total_failures;
const allDataLastRow = 3 + payload.scope.all_failures;
summary.getRangeByIndexes(summaryFirstRow - 1, 0, overallRows.length, 6).values = overallRows;
summary.getRange(`A${summaryTotalRow}:B${summaryTotalRow}`).values = [["Total classified failures", null]];
summary.getRange(`B${summaryTotalRow}`).formulas = [[`=SUM(B${summaryFirstRow}:B${summaryLastRow})`]];
for (let row = summaryFirstRow; row <= summaryLastRow; row += 1) {
  summary.getRange(`B${row}`).formulas = [[`=COUNTIF('Primary Failures'!$I$4:$I$${primaryDataLastRow},A${row})`]];
  summary.getRange(`C${row}`).formulas = [[`=B${row}/$B$${summaryTotalRow}`]];
  summary.getRange(`D${row}`).formulas = [[`=MAX(0,((C${row}+1.96^2/(2*$B$${summaryTotalRow}))-1.96*SQRT((C${row}*(1-C${row})+1.96^2/(4*$B$${summaryTotalRow}))/$B$${summaryTotalRow}))/(1+1.96^2/$B$${summaryTotalRow}))`]];
  summary.getRange(`E${row}`).formulas = [[`=MIN(1,((C${row}+1.96^2/(2*$B$${summaryTotalRow}))+1.96*SQRT((C${row}*(1-C${row})+1.96^2/(4*$B$${summaryTotalRow}))/$B$${summaryTotalRow}))/(1+1.96^2/$B$${summaryTotalRow}))`]];
}
styleBody(summary, `A${summaryFirstRow}:F${summaryLastRow}`);
styleBody(summary, `A${summaryTotalRow}:B${summaryTotalRow}`);
summary.getRange(`A${summaryTotalRow}:B${summaryTotalRow}`).format = { fill: paleGray, font: { name: fontFamily, size: 10, bold: true, color: navy }, borders: { preset: "all", style: "thin", color: border } };
summary.getRange(`C${summaryFirstRow}:E${summaryLastRow}`).format.numberFormat = "0.0%";
summary.getRange("A:A").format.columnWidth = 42;
summary.getRange("B:B").format.columnWidth = 12;
summary.getRange("C:E").format.columnWidth = 18;
summary.getRange("F:F").format.columnWidth = 65;
const chartLastRow = summaryFirstRow + payload.mode_order.filter((mode) => !["Other execution failure", "Unannotated or unclear"].includes(mode)).length - 1;
const overallChart = summary.charts.add("bar", summary.getRange(`A4:B${chartLastRow}`));
overallChart.title = `Primary failure modes across ${payload.scope.total_failures} failed rollouts`;
overallChart.titleTextStyle.fontSize = 12;
overallChart.titleTextStyle.typeface = fontFamily;
overallChart.hasLegend = false;
overallChart.xAxis = { axisType: "textAxis", textStyle: { typeface: fontFamily, fontSize: 9 } };
overallChart.yAxis = { numberFormatCode: "0", numberFormatSourceLinked: false, textStyle: { typeface: fontFamily, fontSize: 9 } };
overallChart.setPosition("H4", "Q23");
summary.freezePanes.freezeRows(4);

// Failure by task formula table
byTask.showGridLines = false;
byTask.mergeCells("A1:G1");
byTask.getRange("A1").values = [["Failure Modes by Task"]];
styleTitle(byTask, "A1:G1");
byTask.mergeCells("A2:G2");
byTask.getRange("A2").values = [["Wilson intervals describe each mode's share among failures for that task; they are descriptive annotation summaries."]];
byTask.getRange("A2:G2").format = { fill: "#FFF2CC", font: { name: fontFamily, size: 9, color: "#5B4300" }, wrapText: true };
byTask.getRange("A4:G4").values = [["Task", "Failure Mode", "Count", "Task Failures", "Share", "Wilson 95% Lower", "Wilson 95% Upper"]];
styleHeader(byTask, "A4:G4");
let taskRow = 5;
for (const task of payload.task_order) {
  for (const mode of payload.mode_order) {
    byTask.getRange(`A${taskRow}:B${taskRow}`).values = [[task, mode]];
    byTask.getRange(`C${taskRow}`).formulas = [[`=COUNTIFS('Primary Failures'!$B$4:$B$${primaryDataLastRow},A${taskRow},'Primary Failures'!$I$4:$I$${primaryDataLastRow},B${taskRow})`]];
    byTask.getRange(`D${taskRow}`).formulas = [[`=COUNTIF('Primary Failures'!$B$4:$B$${primaryDataLastRow},A${taskRow})`]];
    byTask.getRange(`E${taskRow}`).formulas = [[`=C${taskRow}/D${taskRow}`]];
    byTask.getRange(`F${taskRow}`).formulas = [[`=MAX(0,((E${taskRow}+1.96^2/(2*D${taskRow}))-1.96*SQRT((E${taskRow}*(1-E${taskRow})+1.96^2/(4*D${taskRow}))/D${taskRow}))/(1+1.96^2/D${taskRow}))`]];
    byTask.getRange(`G${taskRow}`).formulas = [[`=MIN(1,((E${taskRow}+1.96^2/(2*D${taskRow}))+1.96*SQRT((E${taskRow}*(1-E${taskRow})+1.96^2/(4*D${taskRow}))/D${taskRow}))/(1+1.96^2/D${taskRow}))`]];
    taskRow += 1;
  }
}
styleBody(byTask, `A5:G${taskRow - 1}`);
byTask.getRange(`E5:G${taskRow - 1}`).format.numberFormat = "0.0%";
byTask.getRange("A:A").format.columnWidth = 25;
byTask.getRange("B:B").format.columnWidth = 42;
byTask.getRange("C:D").format.columnWidth = 14;
byTask.getRange("E:G").format.columnWidth = 18;
byTask.freezePanes.freezeRows(4);

// Failure by model formula table
byModel.showGridLines = false;
byModel.mergeCells("A1:G1");
byModel.getRange("A1").values = [["Failure Modes by Model"]];
styleTitle(byModel, "A1:G1");
byModel.mergeCells("A2:G2");
byModel.getRange("A2").values = [["Wilson intervals describe each mode's share among the model's failed novel-spatial-grounding rollouts."]];
byModel.getRange("A2:G2").format = { fill: "#FFF2CC", font: { name: fontFamily, size: 9, color: "#5B4300" }, wrapText: true };
byModel.getRange("A4:G4").values = [["Model", "Failure Mode", "Count", "Model Failures", "Share", "Wilson 95% Lower", "Wilson 95% Upper"]];
styleHeader(byModel, "A4:G4");
let modelRow = 5;
for (const model of payload.complete_models) {
  for (const mode of payload.mode_order) {
    byModel.getRange(`A${modelRow}:B${modelRow}`).values = [[model, mode]];
    byModel.getRange(`C${modelRow}`).formulas = [[`=COUNTIFS('Primary Failures'!$A$4:$A$${primaryDataLastRow},A${modelRow},'Primary Failures'!$I$4:$I$${primaryDataLastRow},B${modelRow})`]];
    byModel.getRange(`D${modelRow}`).formulas = [[`=COUNTIF('Primary Failures'!$A$4:$A$${primaryDataLastRow},A${modelRow})`]];
    byModel.getRange(`E${modelRow}`).formulas = [[`=C${modelRow}/D${modelRow}`]];
    byModel.getRange(`F${modelRow}`).formulas = [[`=MAX(0,((E${modelRow}+1.96^2/(2*D${modelRow}))-1.96*SQRT((E${modelRow}*(1-E${modelRow})+1.96^2/(4*D${modelRow}))/D${modelRow}))/(1+1.96^2/D${modelRow}))`]];
    byModel.getRange(`G${modelRow}`).formulas = [[`=MIN(1,((E${modelRow}+1.96^2/(2*D${modelRow}))+1.96*SQRT((E${modelRow}*(1-E${modelRow})+1.96^2/(4*D${modelRow}))/D${modelRow}))/(1+1.96^2/D${modelRow}))`]];
    modelRow += 1;
  }
}
styleBody(byModel, `A5:G${modelRow - 1}`);
byModel.getRange(`E5:G${modelRow - 1}`).format.numberFormat = "0.0%";
byModel.getRange("A:A").format.columnWidth = 23;
byModel.getRange("B:B").format.columnWidth = 42;
byModel.getRange("C:D").format.columnWidth = 14;
byModel.getRange("E:G").format.columnWidth = 18;
byModel.freezePanes.freezeRows(4);

// All-failure audit summary across every model and condition.
allSummary.showGridLines = false;
allSummary.mergeCells("A1:Q1");
allSummary.getRange("A1").values = [["All Failed Rollouts: Audited Primary Modes"]];
styleTitle(allSummary, "A1:Q1");
allSummary.mergeCells("A2:Q2");
allSummary.getRange("A2").values = [["Includes every failed rollout. Shares and Wilson intervals are conditional on failure and are descriptive; they are not failure rates over all attempts."]];
allSummary.getRange("A2:Q2").format = { fill: "#FFF2CC", font: { name: fontFamily, size: 9, color: "#5B4300" }, wrapText: true };
allSummary.getRange("A4:F4").values = [["Failure Mode", "Count", "Share of Failures", "Wilson 95% Lower", "Wilson 95% Upper", "Interpretation"]];
styleHeader(allSummary, "A4:F4");
const allSummaryFirstRow = 5;
const allSummaryLastRow = allSummaryFirstRow + payload.mode_order.length - 1;
const allSummaryTotalRow = allSummaryLastRow + 2;
allSummary.getRangeByIndexes(allSummaryFirstRow - 1, 0, payload.mode_order.length, 6).values = payload.mode_order.map((mode) => [mode, null, null, null, null, interpretation[mode]]);
allSummary.getRange(`A${allSummaryTotalRow}:B${allSummaryTotalRow}`).values = [["Total failed rollouts", null]];
allSummary.getRange(`B${allSummaryTotalRow}`).formulas = [[`=SUM(B${allSummaryFirstRow}:B${allSummaryLastRow})`]];
for (let row = allSummaryFirstRow; row <= allSummaryLastRow; row += 1) {
  allSummary.getRange(`B${row}`).formulas = [[`=COUNTIF('All Classified Failures'!$I$4:$I$${allDataLastRow},A${row})`]];
  allSummary.getRange(`C${row}`).formulas = [[`=B${row}/$B$${allSummaryTotalRow}`]];
  allSummary.getRange(`D${row}`).formulas = [[`=MAX(0,((C${row}+1.96^2/(2*$B$${allSummaryTotalRow}))-1.96*SQRT((C${row}*(1-C${row})+1.96^2/(4*$B$${allSummaryTotalRow}))/$B$${allSummaryTotalRow}))/(1+1.96^2/$B$${allSummaryTotalRow}))`]];
  allSummary.getRange(`E${row}`).formulas = [[`=MIN(1,((C${row}+1.96^2/(2*$B$${allSummaryTotalRow}))+1.96*SQRT((C${row}*(1-C${row})+1.96^2/(4*$B$${allSummaryTotalRow}))/$B$${allSummaryTotalRow}))/(1+1.96^2/$B$${allSummaryTotalRow}))`]];
}
styleBody(allSummary, `A${allSummaryFirstRow}:F${allSummaryLastRow}`);
styleBody(allSummary, `A${allSummaryTotalRow}:B${allSummaryTotalRow}`);
allSummary.getRange(`A${allSummaryTotalRow}:B${allSummaryTotalRow}`).format = { fill: paleGray, font: { name: fontFamily, size: 10, bold: true, color: navy }, borders: { preset: "all", style: "thin", color: border } };
allSummary.getRange(`C${allSummaryFirstRow}:E${allSummaryLastRow}`).format.numberFormat = "0.0%";
allSummary.getRange("A:A").format.columnWidth = 42;
allSummary.getRange("B:B").format.columnWidth = 12;
allSummary.getRange("C:E").format.columnWidth = 18;
allSummary.getRange("F:F").format.columnWidth = 65;
const allChartLastRow = allSummaryFirstRow + payload.mode_order.filter((mode) => !["Other execution failure", "Unannotated or unclear"].includes(mode)).length - 1;
const allFailureChart = allSummary.charts.add("bar", allSummary.getRange(`A4:B${allChartLastRow}`));
allFailureChart.title = `Primary modes across ${payload.scope.all_failures} failed rollouts`;
allFailureChart.titleTextStyle.fontSize = 12;
allFailureChart.titleTextStyle.typeface = fontFamily;
allFailureChart.hasLegend = false;
allFailureChart.xAxis = { axisType: "textAxis", textStyle: { typeface: fontFamily, fontSize: 9 } };
allFailureChart.yAxis = { numberFormatCode: "0", numberFormatSourceLinked: false, textStyle: { typeface: fontFamily, fontSize: 9 } };
allFailureChart.setPosition("H4", "Q24");
allSummary.freezePanes.freezeRows(4);

// Diagnostic breakdown by evaluation condition.
byCondition.showGridLines = false;
byCondition.mergeCells("A1:G1");
byCondition.getRange("A1").values = [["Failure Modes by Evaluation Condition"]];
styleTitle(byCondition, "A1:G1");
byCondition.mergeCells("A2:G2");
byCondition.getRange("A2").values = [["Counts describe the composition of failures within each condition. Because attempted-rollout denominators differ, do not compare these shares as condition-level failure rates."]];
byCondition.getRange("A2:G2").format = { fill: "#FFF2CC", font: { name: fontFamily, size: 9, color: "#5B4300" }, wrapText: true };
byCondition.getRange("A4:G4").values = [["Condition", "Failure Mode", "Count", "Condition Failures", "Share", "Wilson 95% Lower", "Wilson 95% Upper"]];
styleHeader(byCondition, "A4:G4");
let conditionRow = 5;
for (const condition of payload.condition_order) {
  for (const mode of payload.mode_order) {
    byCondition.getRange(`A${conditionRow}:B${conditionRow}`).values = [[condition, mode]];
    byCondition.getRange(`C${conditionRow}`).formulas = [[`=COUNTIFS('All Classified Failures'!$D$4:$D$${allDataLastRow},A${conditionRow},'All Classified Failures'!$I$4:$I$${allDataLastRow},B${conditionRow})`]];
    byCondition.getRange(`D${conditionRow}`).formulas = [[`=COUNTIF('All Classified Failures'!$D$4:$D$${allDataLastRow},A${conditionRow})`]];
    byCondition.getRange(`E${conditionRow}`).formulas = [[`=C${conditionRow}/D${conditionRow}`]];
    byCondition.getRange(`F${conditionRow}`).formulas = [[`=MAX(0,((E${conditionRow}+1.96^2/(2*D${conditionRow}))-1.96*SQRT((E${conditionRow}*(1-E${conditionRow})+1.96^2/(4*D${conditionRow}))/D${conditionRow}))/(1+1.96^2/D${conditionRow}))`]];
    byCondition.getRange(`G${conditionRow}`).formulas = [[`=MIN(1,((E${conditionRow}+1.96^2/(2*D${conditionRow}))+1.96*SQRT((E${conditionRow}*(1-E${conditionRow})+1.96^2/(4*D${conditionRow}))/D${conditionRow}))/(1+1.96^2/D${conditionRow}))`]];
    conditionRow += 1;
  }
}
styleBody(byCondition, `A5:G${conditionRow - 1}`);
byCondition.getRange(`E5:G${conditionRow - 1}`).format.numberFormat = "0.0%";
byCondition.getRange("A:A").format.columnWidth = 43;
byCondition.getRange("B:B").format.columnWidth = 42;
byCondition.getRange("C:D").format.columnWidth = 14;
byCondition.getRange("E:G").format.columnWidth = 18;
byCondition.freezePanes.freezeRows(4);

// Small, editable queue for the user's video/annotation review.
reviewQueue.showGridLines = false;
reviewQueue.mergeCells("A1:O1");
reviewQueue.getRange("A1").values = [["Rollouts Requiring Confirmation"]];
styleTitle(reviewQueue, "A1:O1");
reviewQueue.mergeCells("A2:O2");
reviewQueue.getRange("A2").values = [[payload.scope.review_queue === 0
  ? "All previously queued rollouts were reviewed. No unresolved failure labels remain."
  : "Yellow columns are intentionally blank for reviewer input. Suggested labels remain in the audited data until a confirmed replacement is entered and propagated."]];
reviewQueue.getRange("A2:O2").format = { fill: "#FFF2CC", font: { name: fontFamily, size: 9, color: "#5B4300" }, wrapText: true };
const reviewHeaders = [
  "Model", "Task", "Episode", "Condition", "Prompt", "Expected Target / Action",
  "Current Observation", "Suggested Primary Mode", "Current Secondary Flags", "Confidence",
  "Why Review Needed", "Reviewer Observation", "Confirmed Primary Mode", "Confirmed Secondary Flags", "Reviewed?",
];
const reviewRows = payload.review_queue.map((r) => [
  safe(r.Model), safe(r["Canonical Task"]), safe(r.Episode), safe(r.Condition), safe(r.Prompt),
  safe(r["Expected Target / Action"]), safe(r.Observation), safe(r["Primary Failure Mode"]),
  safe(r["Secondary Flags"]), safe(r["Classification Confidence"]), safe(r["Why Review Needed"]),
  "", "", "", "No",
]);
writeTable(reviewQueue, 2, 0, reviewHeaders, reviewRows, "ReviewQueueTable");
const reviewLastRow = 3 + reviewRows.length;
if (reviewRows.length) {
  reviewQueue.getRange(`L4:O${reviewLastRow}`).format.fill = "#FFF2CC";
  reviewQueue.getRange(`M4:M${reviewLastRow}`).dataValidation = { rule: { type: "list", values: payload.mode_order } };
  reviewQueue.getRange(`O4:O${reviewLastRow}`).dataValidation = { rule: { type: "list", values: ["No", "Yes"] } };
}
reviewQueue.getRange("A:A").format.columnWidth = 21;
reviewQueue.getRange("B:B").format.columnWidth = 24;
reviewQueue.getRange("C:C").format.columnWidth = 9;
reviewQueue.getRange("D:D").format.columnWidth = 35;
reviewQueue.getRange("E:G").format.columnWidth = 43;
reviewQueue.getRange("H:I").format.columnWidth = 34;
reviewQueue.getRange("J:J").format.columnWidth = 14;
reviewQueue.getRange("K:N").format.columnWidth = 40;
reviewQueue.getRange("O:O").format.columnWidth = 12;
reviewQueue.freezePanes.freezeRows(3);
reviewQueue.freezePanes.freezeColumns(3);

// Task-name map
names.showGridLines = false;
names.mergeCells("A1:C1");
names.getRange("A1").values = [["Canonical Spa-Bench Task Names"]];
styleTitle(names, "A1:C1");
const nameRows = [
  ["State Recognition", "Physical State", "Use canonical name in prose, figures, captions, and tables."],
  ["Size Recognition", "Relative Size", "Use canonical name in prose, figures, captions, and tables."],
  ["Referential Disambiguation", "Referential Description", "Use canonical name in prose, figures, captions, and tables."],
  ["Ordering/Sequencing", "Ordinal Position", "Use canonical name in prose, figures, captions, and tables."],
  ["Relational Placement", "Relational Placement", "Already canonical."],
  ["Counting", "Counting", "Already canonical."],
];
writeTable(names, 2, 0, ["Legacy Name", "Canonical Name", "Instruction"], nameRows, "TaskNameMapTable");
names.getRange("A:B").format.columnWidth = 30;
names.getRange("C:C").format.columnWidth = 55;
names.freezePanes.freezeRows(3);

// Methods and category definitions
methods.showGridLines = false;
methods.mergeCells("A1:D1");
methods.getRange("A1").values = [["Failure Audit Methods and Definitions"]];
styleTitle(methods, "A1:D1");
methods.getRange("A3:B12").values = [
  ["All-failure population", `All ${payload.scope.all_failures} failed rollouts across the five evaluated model variants and every recorded evaluation condition.`],
  ["Primary-paper population", "Failed novel-spatial-grounding rollouts from GR00T Frozen LLM, Pi0.5, and MolmoAct2."],
  ["Classification source", "User-reviewed free-text qualitative rollout annotations."],
  ["Primary-mode rule", "Each failed rollout receives one mutually exclusive primary category corresponding to the earliest failure that made success impossible; additional observed problems are retained as secondary flags."],
  ["Secondary flags", "Secondary flags are non-exclusive co-occurring observations. They do not change the primary-mode counts and can sum to more than the number of rollouts."],
  ["No-movement rule", "A failed control whose correct behavior was to leave the scene unchanged is classified as Unnecessary intervention. The attempted object or execution problem is retained as a secondary flag where available."],
  ["Manual review", `${payload.scope.review_queue} rows remain in the Review Queue: ${payload.scope.missing_observations} with missing observations and ${payload.scope.ambiguous_nonblank} with provisional labels that need confirmation.`],
  ["Denominator", "All failure-mode shares use failed rollouts as the denominator. They do not estimate the probability of a mode across all attempts."],
  ["Wilson interval", "Two-sided 95% Wilson score interval with z=1.96, calculated for each categorical share."],
  ["Interpretation", "These categories summarize existing annotations; they are not a blinded independent video coding study."],
];
styleBody(methods, "A3:B12");
methods.getRange("A3:A12").format = { fill: paleGray, font: { name: fontFamily, size: 10, bold: true, color: navy }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: border } };
methods.mergeCells("A14:D14");
methods.getRange("A14").values = [["Failure-mode codebook"]];
styleSection(methods, "A14:D14");
const codebookRows = payload.mode_order.map((mode) => [mode, interpretation[mode]]);
writeTable(methods, 14, 0, ["Primary Failure Mode", "Operational Definition"], codebookRows, "FailureCodebookTable");
methods.mergeCells("A28:D28");
methods.getRange("A28").values = [["Sources"]];
styleSection(methods, "A28:D28");
methods.getRange("A29:B31").values = [
  ["Training dataset", "https://huggingface.co/datasets/justintiensmith/VLA_Reasoning_Training_Dataset_1200"],
  ["Attached manifest", payload.source_manifest],
  ["Reviewed classification workbook", payload.source_evaluations],
];
styleBody(methods, "A29:B31");
methods.getRange("A:A").format.columnWidth = 34;
methods.getRange("B:B").format.columnWidth = 95;
methods.getRange("C:D").format.columnWidth = 14;
methods.freezePanes.freezeRows(1);

// Populate headline links after their source formulas have been created.
const modeRow = (mode) => summaryFirstRow + payload.mode_order.indexOf(mode);
readme.getRange("B13:B17").formulas = [
  [`='Failure Summary'!B${summaryTotalRow}`],
  ["='Failure Summary'!B5"],
  ["='Failure Summary'!C5"],
  ["='Failure Summary'!B6"],
  ["='Failure Summary'!C6"],
];
readme.getRange("B19").formulas = [
  [`='Failure Summary'!B${modeRow("Release/retention failure")}`],
];

// Workbook-wide font and tab colors.
for (const sheet of workbook.worksheets.items) {
  sheet.tabColor = navy;
}

// Key inspections before export.
const check = await workbook.inspect({
  kind: "table",
  range: `Failure Summary!A1:F${summaryTotalRow}`,
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 8,
  maxChars: 12000,
});
process.stdout.write(check.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
process.stdout.write(errors.ndjson);

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(renderDir, { recursive: true });
const renderSpecs = [
  ["Read Me", "A1:H25"],
  ["Matrix Gallery", "A1:L43"],
  ["Missing Cell Map", "A1:E35"],
  ["Failure Summary", "A1:Q24"],
  ["Failure by Task", `A1:G${taskRow - 1}`],
  ["Failure by Model", `A1:G${modelRow - 1}`],
  ["All Failure Summary", "A1:Q24"],
  ["Failure by Condition", `A1:G${Math.min(conditionRow - 1, 80)}`],
  ["Review Queue", `A1:O${reviewLastRow}`],
  ["Primary Failures", "A1:M24"],
  ["All Classified Failures", "A1:M24"],
  ["Task Names", "A1:C10"],
  ["Methods", "A1:D31"],
];
for (const [sheetName, range] of renderSpecs) {
  const preview = await workbook.render({ sheetName, range, scale: 0.9, format: "png" });
  const safeName = sheetName.toLowerCase().replaceAll(" ", "_");
  await fs.writeFile(path.join(renderDir, `${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
process.stdout.write(`\nSAVED ${outputPath}\n`);
