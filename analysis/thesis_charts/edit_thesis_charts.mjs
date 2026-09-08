import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";


const sourcePath = "/Users/justintiensmith/Documents/MSc_Thesis_Bar_Charts.xlsx";
const workDir = "/Users/justintiensmith/Documents/lerobot/output/thesis_bar_charts_audit";
const outputDir = "/Users/justintiensmith/Documents/lerobot/outputs/01a0678e-4e7e-7a31-b018-7fba72ab9fe5";
const outputPath = path.join(outputDir, "MSc_Thesis_Bar_Charts_Verified_with_CIs.xlsx");
const expected = JSON.parse(await fs.readFile(path.join(workDir, "expected_chart_data.json"), "utf8"));
const failureData = JSON.parse(await fs.readFile(path.join(workDir, "failure_chart_data.json"), "utf8"));
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath));

const modelHeader = {
  "GR00T Frozen LLM": "GR00T Frozen LLM",
  "GR00T Full FT": "GR00T-N1.7 Full FT",
  "Pi0.5": "$\\pi_{0.5}$",
  "MolmoAct2": "MolmoAct2",
  "VLA-0": "VLA-0",
};

function qSheet(name) {
  return `'${name.replaceAll("'", "''")}'`;
}

function rowBy(rows, keys) {
  const matches = rows.filter((row) => Object.entries(keys).every(([key, value]) => row[key] === value));
  if (matches.length !== 1) {
    throw new Error(`Expected one row for ${JSON.stringify(keys)}; found ${matches.length}`);
  }
  return matches[0];
}

function setValues(sheet, address, values) {
  sheet.getRange(address).values = values;
}

function setFormulas(sheet, address, formulas) {
  sheet.getRange(address).formulas = formulas;
}

function errorFormula(rateCell, boundCell, lower) {
  return lower ? `=${rateCell}-${boundCell}` : `=${boundCell}-${rateCell}`;
}

function addCustomErrorBars(series, sheetName, minusRange, plusRange) {
  series.errorBars = {
    type: "custom",
    direction: "both",
    endStyle: "cap",
    minusFormula: `${qSheet(sheetName)}!${minusRange}`,
    plusFormula: `${qSheet(sheetName)}!${plusRange}`,
  };
}

function applyThreeModelErrors(sheetName, chart, startRow, endRow, errorColumns) {
  const models = ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"];
  for (let i = 0; i < models.length; i += 1) {
    addCustomErrorBars(
      chart.series.items[i],
      sheetName,
      `$${errorColumns[i][0]}$${startRow}:$${errorColumns[i][0]}$${endRow}`,
      `$${errorColumns[i][1]}$${startRow}:$${errorColumns[i][1]}$${endRow}`,
    );
  }
}

// Familiar spatial grounding: five models, six tasks.
{
  const sheetName = "Familiar Spatial Task Chart";
  const sheet = workbook.worksheets.getItem(sheetName);
  const rows = expected[sheetName];
  const tasks = [
    ["Counting", "Counting"],
    ["Ordering by Ordinal Reference", "Ordinal Reference Ordering"],
    ["Relational Placement", "Relational Placement"],
    ["State Recognition", "State Recognition"],
    ["Relative Size Recognition", "Size Recognition"],
    ["Referential Disambiguation", "Referential Disambiguation"],
  ];
  const models = ["VLA-0", "GR00T Full FT", "GR00T Frozen LLM", "Pi0.5", "MolmoAct2"];
  const rateCols = ["B", "C", "D", "E", "F"];
  const ciCols = [["G", "H"], ["I", "J"], ["K", "L"], ["M", "N"], ["O", "P"]];
  const scoredCols = ["Q", "R", "S", "T", "U"];
  const errorCols = [["V", "W"], ["X", "Y"], ["Z", "AA"], ["AB", "AC"], ["AD", "AE"]];
  setValues(sheet, "B1:F1", [models.map((model) => modelHeader[model])]);
  for (let i = 0; i < tasks.length; i += 1) {
    const excelRow = i + 2;
    setValues(sheet, `A${excelRow}`, [[tasks[i][0]]]);
    for (let j = 0; j < models.length; j += 1) {
      const datum = rowBy(rows, { Task: tasks[i][1], Model: models[j] });
      setValues(sheet, `${rateCols[j]}${excelRow}`, [[datum.Rate]]);
      setValues(sheet, `${ciCols[j][0]}${excelRow}:${ciCols[j][1]}${excelRow}`, [[datum["CI Lower"], datum["CI Upper"]]]);
      setValues(sheet, `${scoredCols[j]}${excelRow}`, [[datum.Scored]]);
      setFormulas(sheet, `${errorCols[j][0]}${excelRow}:${errorCols[j][1]}${excelRow}`, [[
        errorFormula(`${rateCols[j]}${excelRow}`, `${ciCols[j][0]}${excelRow}`, true),
        errorFormula(`${rateCols[j]}${excelRow}`, `${ciCols[j][1]}${excelRow}`, false),
      ]]);
    }
  }
  const chart = sheet.charts.items[0];
  for (let i = 0; i < 5; i += 1) {
    addCustomErrorBars(
      chart.series.items[i],
      sheetName,
      `$${errorCols[i][0]}$2:$${errorCols[i][0]}$7`,
      `$${errorCols[i][1]}$2:$${errorCols[i][1]}$7`,
    );
  }
}

// Three-model task charts.
for (const config of [
  { sheetName: "Matched Manipulation Task Chart", expectedName: "Matched Manipulation Task Chart", taskCount: 6 },
  { sheetName: "Novel Spatial Task Chart", expectedName: "Novel Spatial Task Chart", taskCount: 6 },
]) {
  const sheet = workbook.worksheets.getItem(config.sheetName);
  const rows = expected[config.expectedName];
  const tasks = [
    ["Counting", "Counting"],
    ["Ordering by Ordinal Reference", "Ordinal Reference Ordering"],
    ["Relational Placement", "Relational Placement"],
    ["State Recognition", "State Recognition"],
    ["Relative Size Recognition", "Size Recognition"],
    ["Referential Disambiguation", "Referential Disambiguation"],
  ];
  const models = ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"];
  setValues(sheet, "B1:D1", [[modelHeader[models[0]], "Pi0.5", modelHeader[models[2]]]]);
  setValues(sheet, "N1:S1", [[
    "GR00T Lower error", "GR00T Upper error",
    "Pi0.5 Lower error", "Pi0.5 Upper error",
    "MolmoAct2 Lower error", "MolmoAct2 Upper error",
  ]]);
  for (let i = 0; i < tasks.length; i += 1) {
    const excelRow = i + 2;
    setValues(sheet, `A${excelRow}`, [[tasks[i][0]]]);
    const rowValues = [];
    const bounds = [];
    const scored = [];
    for (const model of models) {
      const datum = rowBy(rows, { Task: tasks[i][1], Model: model });
      rowValues.push(datum.Rate);
      bounds.push(datum["CI Lower"], datum["CI Upper"]);
      scored.push(datum.Scored);
    }
    setValues(sheet, `B${excelRow}:D${excelRow}`, [rowValues]);
    setValues(sheet, `E${excelRow}:J${excelRow}`, [bounds]);
    setValues(sheet, `K${excelRow}:M${excelRow}`, [scored]);
    setFormulas(sheet, `N${excelRow}:S${excelRow}`, [[
      errorFormula(`B${excelRow}`, `E${excelRow}`, true), errorFormula(`B${excelRow}`, `F${excelRow}`, false),
      errorFormula(`C${excelRow}`, `G${excelRow}`, true), errorFormula(`C${excelRow}`, `H${excelRow}`, false),
      errorFormula(`D${excelRow}`, `I${excelRow}`, true), errorFormula(`D${excelRow}`, `J${excelRow}`, false),
    ]]);
  }
  applyThreeModelErrors(config.sheetName, sheet.charts.items[0], 2, 7, [["N", "O"], ["P", "Q"], ["R", "S"]]);
}

// No-movement diagnostics across four tasks and aggregate.
{
  const sheetName = "No Movement";
  const sheet = workbook.worksheets.getItem(sheetName);
  const rows = expected[sheetName];
  const rowKeys = [
    ["Counting: goal already satisfied", { Task: "Counting", Condition: "Goal already satisfied / no movement" }],
    ["Ordinal Position: invalid ordinal", { Task: "Ordinal Reference Ordering", Condition: "Invalid ordinal / no-movement diagnostic" }],
    ["Physical State: no valid target", { Task: "State Recognition", Condition: "No valid target / no movement" }],
    ["Referential Description: no valid candidate", { Task: "Referential Disambiguation", Condition: "No valid candidate category / no movement" }],
    ["Aggregate across four tasks", { Task: "Aggregate across four tasks", Condition: "Aggregate" }],
  ];
  const models = ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"];
  for (let i = 0; i < rowKeys.length; i += 1) {
    const excelRow = i + 2;
    setValues(sheet, `A${excelRow}`, [[rowKeys[i][0]]]);
    const data = models.map((model) => rowBy(rows, { ...rowKeys[i][1], Model: model }));
    setValues(sheet, `B${excelRow}:D${excelRow}`, [[...data.map((d) => d.Rate)]]);
    setValues(sheet, `E${excelRow}:J${excelRow}`, [[...data.flatMap((d) => [d["CI Lower"], d["CI Upper"]])]]);
    setValues(sheet, `K${excelRow}:M${excelRow}`, [[...data.map((d) => d.Scored)]]);
    setFormulas(sheet, `N${excelRow}:S${excelRow}`, [[
      errorFormula(`B${excelRow}`, `E${excelRow}`, true), errorFormula(`B${excelRow}`, `F${excelRow}`, false),
      errorFormula(`C${excelRow}`, `G${excelRow}`, true), errorFormula(`C${excelRow}`, `H${excelRow}`, false),
      errorFormula(`D${excelRow}`, `I${excelRow}`, true), errorFormula(`D${excelRow}`, `J${excelRow}`, false),
    ]]);
  }
  applyThreeModelErrors(sheetName, sheet.charts.items[0], 2, 6, [["N", "O"], ["P", "Q"], ["R", "S"]]);
}

// Relational no-movement versus corrective movement.
{
  const sheetName = "Relational Movement No Movement";
  const sheet = workbook.worksheets.getItem(sheetName);
  const rows = expected[sheetName];
  const configs = [
    ["Relational goal already satisfied / no movement", "Goal already satisfied / no movement"],
    ["Relational corrective movement required", "Violated-relation correction control"],
  ];
  const models = ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"];
  setValues(sheet, "N1:S1", [[
    "GR00T Lower error", "GR00T Upper error", "Pi0.5 Lower error", "Pi0.5 Upper error", "MolmoAct2 Lower error", "MolmoAct2 Upper error",
  ]]);
  for (let i = 0; i < configs.length; i += 1) {
    const excelRow = i + 2;
    const data = models.map((model) => rowBy(rows, { Condition: configs[i][1], Model: model }));
    setValues(sheet, `A${excelRow}`, [[configs[i][0]]]);
    setValues(sheet, `B${excelRow}:D${excelRow}`, [[...data.map((d) => d.Rate)]]);
    setValues(sheet, `E${excelRow}:J${excelRow}`, [[...data.flatMap((d) => [d["CI Lower"], d["CI Upper"]])]]);
    setValues(sheet, `K${excelRow}:M${excelRow}`, [[...data.map((d) => d.Scored)]]);
    setFormulas(sheet, `N${excelRow}:S${excelRow}`, [[
      errorFormula(`B${excelRow}`, `E${excelRow}`, true), errorFormula(`B${excelRow}`, `F${excelRow}`, false),
      errorFormula(`C${excelRow}`, `G${excelRow}`, true), errorFormula(`C${excelRow}`, `H${excelRow}`, false),
      errorFormula(`D${excelRow}`, `I${excelRow}`, true), errorFormula(`D${excelRow}`, `J${excelRow}`, false),
    ]]);
  }
  applyThreeModelErrors(sheetName, sheet.charts.items[0], 2, 3, [["N", "O"], ["P", "Q"], ["R", "S"]]);
}

// Standard objects versus cross-task objects.
{
  const sheetName = "Cross Task Object Chart v2";
  const sheet = workbook.worksheets.getItem(sheetName);
  const rows = expected[sheetName];
  const categories = [
    "Familiar spatial grounding, standard objects",
    "Familiar spatial grounding, cross-task objects",
  ];
  const models = ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"];
  setValues(sheet, "N1:S1", [[
    "GR00T Lower error", "GR00T Upper error", "Pi0.5 Lower error", "Pi0.5 Upper error", "MolmoAct2 Lower error", "MolmoAct2 Upper error",
  ]]);
  for (let i = 0; i < categories.length; i += 1) {
    const excelRow = i + 2;
    const data = models.map((model) => rowBy(rows, { Category: categories[i], Model: model }));
    setValues(sheet, `A${excelRow}`, [[categories[i]]]);
    setValues(sheet, `B${excelRow}:D${excelRow}`, [[...data.map((d) => d.Rate)]]);
    setValues(sheet, `E${excelRow}:J${excelRow}`, [[...data.flatMap((d) => [d["CI Lower"], d["CI Upper"]])]]);
    setValues(sheet, `K${excelRow}:M${excelRow}`, [[...data.map((d) => d.Scored)]]);
    setFormulas(sheet, `N${excelRow}:S${excelRow}`, [[
      errorFormula(`B${excelRow}`, `E${excelRow}`, true), errorFormula(`B${excelRow}`, `F${excelRow}`, false),
      errorFormula(`C${excelRow}`, `G${excelRow}`, true), errorFormula(`C${excelRow}`, `H${excelRow}`, false),
      errorFormula(`D${excelRow}`, `I${excelRow}`, true), errorFormula(`D${excelRow}`, `J${excelRow}`, false),
    ]]);
  }
  applyThreeModelErrors(sheetName, sheet.charts.items[0], 2, 3, [["N", "O"], ["P", "Q"], ["R", "S"]]);
}

// Original versus paraphrased instructions, using only the corresponding 60 matched scenes.
{
  const sheetName = "Paraphrasing Comparison v3";
  const sheet = workbook.worksheets.getItem(sheetName);
  const rows = expected[sheetName];
  const groups = ["Matched Manipulation", "Novel Spatial Grounding"];
  const models = ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"];
  const mainRows = [
    [2, groups[0], "Original"],
    [3, groups[0], "Paraphrased"],
    [4, groups[1], "Original"],
    [5, groups[1], "Paraphrased"],
  ];
  setValues(sheet, "B1:D1", [[modelHeader[models[0]], "Pi0.5", modelHeader[models[2]]]]);
  for (const [excelRow, group, phrasing] of mainRows) {
    const data = models.map((model) => rowBy(rows, { Group: group, Model: model, Phrasing: phrasing }));
    setValues(sheet, `B${excelRow}:D${excelRow}`, [[...data.map((d) => d.Rate)]]);
    setValues(sheet, `E${excelRow}:J${excelRow}`, [[...data.flatMap((d) => [d["CI Lower"], d["CI Upper"]])]]);
    setValues(sheet, `K${excelRow}:M${excelRow}`, [[...data.map((d) => d.Successes)]]);
    setValues(sheet, `N${excelRow}:P${excelRow}`, [[...data.map((d) => d.Scored)]]);
  }
  setValues(sheet, "Q1:X1", [["Group", "Model", "Original", "Paraphrased", "Original Lower error", "Original Upper error", "Paraphrased Lower error", "Paraphrased Upper error"]]);
  const helperRows = [];
  for (const group of groups) {
    for (const model of models) {
      const original = rowBy(rows, { Group: group, Model: model, Phrasing: "Original" });
      const paraphrased = rowBy(rows, { Group: group, Model: model, Phrasing: "Paraphrased" });
      helperRows.push([
        group,
        modelHeader[model],
        original.Rate,
        paraphrased.Rate,
        original["Lower Error"],
        original["Upper Error"],
        paraphrased["Lower Error"],
        paraphrased["Upper Error"],
      ]);
    }
    if (group === groups[0]) helperRows.push([null, null, null, null, null, null, null, null]);
  }
  setValues(sheet, "Q2:X8", helperRows);
  const chart = sheet.charts.items[0];
  addCustomErrorBars(chart.series.items[0], sheetName, "$U$2:$U$8", "$V$2:$V$8");
  addCustomErrorBars(chart.series.items[1], sheetName, "$W$2:$W$8", "$X$2:$X$8");
}

// Compact overall comparison.
{
  const sheetName = "Emergent Skills Data";
  const sheet = workbook.worksheets.getItem(sheetName);
  const rows = expected[sheetName];
  const tracks = [
    ["Matched Manipulation Control", "Matched Manipulation Control"],
    ["Familiar Spatial Grounding", "Familiar Spatial Concepts"],
    ["Novel Spatial Grounding", "Novel Spatial Concepts"],
  ];
  const models = ["GR00T Frozen LLM", "Pi0.5", "MolmoAct2"];
  setValues(sheet, "B1:D1", [[modelHeader[models[0]], "Pi0.5", modelHeader[models[2]]]]);
  setValues(sheet, "E1:V1", [[
    "GR00T Successes", "Pi0.5 Successes", "MolmoAct2 Successes",
    "GR00T Scored", "Pi0.5 Scored", "MolmoAct2 Scored",
    "GR00T CI lower", "GR00T CI upper", "Pi0.5 CI lower", "Pi0.5 CI upper", "MolmoAct2 CI lower", "MolmoAct2 CI upper",
    "GR00T Lower error", "GR00T Upper error", "Pi0.5 Lower error", "Pi0.5 Upper error", "MolmoAct2 Lower error", "MolmoAct2 Upper error",
  ]]);
  for (let i = 0; i < tracks.length; i += 1) {
    const excelRow = i + 2;
    const data = models.map((model) => rowBy(rows, { "Evaluation track": tracks[i][1], Model: model }));
    setValues(sheet, `A${excelRow}:D${excelRow}`, [[tracks[i][0], ...data.map((d) => d.Rate)]]);
    setValues(sheet, `E${excelRow}:G${excelRow}`, [[...data.map((d) => d.Successes)]]);
    setValues(sheet, `H${excelRow}:J${excelRow}`, [[...data.map((d) => d.Scored)]]);
    setValues(sheet, `K${excelRow}:P${excelRow}`, [[...data.flatMap((d) => [d["CI Lower"], d["CI Upper"]])]]);
    setFormulas(sheet, `Q${excelRow}:V${excelRow}`, [[
      errorFormula(`B${excelRow}`, `K${excelRow}`, true), errorFormula(`B${excelRow}`, `L${excelRow}`, false),
      errorFormula(`C${excelRow}`, `M${excelRow}`, true), errorFormula(`C${excelRow}`, `N${excelRow}`, false),
      errorFormula(`D${excelRow}`, `O${excelRow}`, true), errorFormula(`D${excelRow}`, `P${excelRow}`, false),
    ]]);
  }
  applyThreeModelErrors(sheetName, sheet.charts.items[0], 2, 4, [["Q", "R"], ["S", "T"], ["U", "V"]]);
}

// Detailed overall table and its local chart helper.
{
  const sheetName = "Sheet2";
  const sheet = workbook.worksheets.getItem(sheetName);
  const rows = expected[sheetName];
  const rowMap = [
    [5, "Novel Spatial Concepts", "MolmoAct2"], [6, "Novel Spatial Concepts", "Pi0.5"], [7, "Novel Spatial Concepts", "GR00T Frozen LLM"],
    [8, "Familiar Spatial Concepts", "MolmoAct2"], [9, "Familiar Spatial Concepts", "Pi0.5"], [10, "Familiar Spatial Concepts", "GR00T Frozen LLM"],
    [11, "Matched Manipulation Control", "MolmoAct2"], [12, "Matched Manipulation Control", "Pi0.5"], [13, "Matched Manipulation Control", "GR00T Frozen LLM"],
  ];
  for (const [excelRow, track, model] of rowMap) {
    const datum = rowBy(rows, { "Evaluation track": track, Model: model });
    setValues(sheet, `B${excelRow}:K${excelRow}`, [[
      model === "Pi0.5" ? "π0.5" : modelHeader[model],
      "Complete benchmark",
      datum.Successes,
      datum.Scored - datum.Successes,
      datum.Scored,
      datum.Rate,
      datum["CI Lower"],
      datum["CI Upper"],
      datum["Lower Error"],
      datum["Upper Error"],
    ]]);
    setValues(sheet, `L${excelRow}`, [[`${(datum.Rate * 100).toFixed(1)}% [${(datum["CI Lower"] * 100).toFixed(1)}%–${(datum["CI Upper"] * 100).toFixed(1)}%]`]]);
  }
  setValues(sheet, "Q4:X4", [["Evaluation track", "MolmoAct2", "π0.5", "GR00T Frozen LLM", "Molmo lower", "Molmo upper", "Pi lower", "Pi upper"]]);
  const tracks = ["Novel Spatial Concepts", "Familiar Spatial Concepts", "Matched Manipulation Control"];
  const helper = [];
  for (const track of tracks) {
    const molmo = rowBy(rows, { "Evaluation track": track, Model: "MolmoAct2" });
    const pi = rowBy(rows, { "Evaluation track": track, Model: "Pi0.5" });
    const groot = rowBy(rows, { "Evaluation track": track, Model: "GR00T Frozen LLM" });
    helper.push([track, molmo.Rate, pi.Rate, groot.Rate, molmo["Lower Error"], molmo["Upper Error"], pi["Lower Error"], pi["Upper Error"], groot["Lower Error"], groot["Upper Error"]]);
  }
  setValues(sheet, "Q5:Z7", helper);
  setValues(sheet, "Y4:Z4", [["GR00T lower", "GR00T upper"]]);
  const chart = sheet.charts.items[0];
  chart.setData(sheet.getRange("Q4:T7"));
  const colors = ["#E67E00", "#07966A", "#2F67E8"];
  const errors = [["U", "V"], ["W", "X"], ["Y", "Z"]];
  for (let i = 0; i < chart.series.items.length; i += 1) {
    chart.series.items[i].fill = colors[i];
    addCustomErrorBars(chart.series.items[i], sheetName, `$${errors[i][0]}$5:$${errors[i][0]}$7`, `$${errors[i][1]}$5:$${errors[i][1]}$7`);
  }
}

function addFailureSheet(sheetName, title, payload) {
  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;
  const rows = [...payload.rows].sort((a, b) => b.Count - a.Count);
  setValues(sheet, "A1", [[title]]);
  setValues(sheet, "A2", [[`${payload.scope}. Shares and Wilson intervals are conditional on failure (n=${payload.total}).`]]);
  setValues(sheet, "A3", [["Source: Spa_Bench_All_Failure_Audit.xlsx."]]);
  setValues(sheet, `A5:G${rows.length + 5}`, [
    ["Failure mode", "Count", "Share of failures", "Wilson 95% lower", "Wilson 95% upper", "Lower error", "Upper error"],
    ...rows.map((row) => [row["Failure Mode"], row.Count, row.Share, row["CI Lower"], row["CI Upper"], row.Share - row["CI Lower"], row["CI Upper"] - row.Share]),
  ]);
  sheet.getRange("A1:G1").format.font = { name: "Arial", size: 14, bold: true, color: "#1F1F1F" };
  sheet.getRange("A2:G3").format.font = { name: "Arial", size: 10, italic: true, color: "#595959" };
  sheet.getRange("A5:G5").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" } };
  sheet.getRange(`A6:G${rows.length + 5}`).format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
  sheet.getRange(`C6:G${rows.length + 5}`).format.numberFormat = "0.0%";
  sheet.getRange(`B6:B${rows.length + 5}`).format.numberFormat = "#,##0";
  sheet.getRange(`A5:G${rows.length + 5}`).format.borders = { preset: "insideHorizontal", style: "thin", color: "#D9E2F3" };
  sheet.getRange("A:A").format.columnWidth = 42;
  sheet.getRange("B:B").format.columnWidth = 11;
  sheet.getRange("C:G").format.columnWidth = 16;
  const chart = sheet.charts.add("bar", [sheet.getRange(`A5:A${rows.length + 5}`), sheet.getRange(`C5:C${rows.length + 5}`)]);
  chart.title = title;
  chart.titleTextStyle.fontSize = 14;
  chart.titleTextStyle.typeface = "Arial";
  chart.hasLegend = false;
  chart.xAxis = { axisType: "textAxis", textStyle: { typeface: "Arial", fontSize: 10 } };
  chart.yAxis = { numberFormatCode: "0%", numberFormatSourceLinked: false, textStyle: { typeface: "Arial", fontSize: 10 }, minimumScale: 0, maximumScale: 0.6 };
  chart.setPosition("I2", "T25");
  chart.series.items[0].fill = "#4F81BD";
  addCustomErrorBars(chart.series.items[0], sheetName, `$F$6:$F$${rows.length + 5}`, `$G$6:$G$${rows.length + 5}`);
  return sheet;
}

addFailureSheet("Failure Analysis - Novel", "Failure modes in novel spatial grounding", failureData.Novel);
addFailureSheet("Failure Analysis - All", "Failure modes across all failed rollouts", failureData.All);

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
process.stdout.write(JSON.stringify({ outputPath }, null, 2));
