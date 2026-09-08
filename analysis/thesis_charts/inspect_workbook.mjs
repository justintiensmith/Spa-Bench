import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = process.argv[2];
const outputDir = process.argv[3];
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

const summary = [];
for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  const charts = sheet.charts.items.map((chart) => ({
    name: chart.name,
    type: chart.type,
    title: chart.title?.text ?? chart.title ?? null,
    left: chart.left,
    top: chart.top,
    width: chart.width,
    height: chart.height,
    series: chart.series.items.map((series) => ({
      name: series.name,
      formula: series.formula,
      categoryFormula: series.categoryFormula,
      fill: series.fill,
    })),
  }));
  summary.push({
    name: sheet.name,
    usedRange: used?.address ?? null,
    chartCount: charts.length,
    charts,
    tableCount: sheet.tables.items.length,
  });
}

await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(path.join(outputDir, "workbook_structure.json"), JSON.stringify(summary, null, 2));
process.stdout.write(JSON.stringify(summary, null, 2));
