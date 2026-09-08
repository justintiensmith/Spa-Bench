import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "/Users/justintiensmith/Documents/lerobot/outputs/01a0678e-4e7e-7a31-b018-7fba72ab9fe5/MSc_Thesis_Bar_Charts_Verified_with_CIs.xlsx";
const outputDir = "/Users/justintiensmith/Documents/lerobot/output/thesis_bar_charts_audit/final_previews";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

const checks = {};
for (const [sheetName, range] of [
  ["Paraphrasing Comparison v3", "A1:X8"],
  ["Familiar Spatial Task Chart", "A1:AE7"],
  ["Novel Spatial Task Chart", "A1:S7"],
  ["Sheet2", "A4:Z13"],
  ["Failure Analysis - Novel", "A1:G13"],
  ["Failure Analysis - All", "A1:G14"],
]) {
  const result = await workbook.inspect({
    kind: "table",
    range: `'${sheetName}'!${range}`,
    include: "values,formulas",
    tableMaxRows: 20,
    tableMaxCols: 31,
  });
  checks[sheetName] = result.ndjson;
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});

await fs.mkdir(outputDir, { recursive: true });
for (const [sheetName, range, filename] of [
  ["Failure Analysis - Novel", "A1:T25", "failure_novel.png"],
  ["Failure Analysis - All", "A1:T25", "failure_all.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(outputDir, filename), new Uint8Array(await preview.arrayBuffer()));
}

await fs.writeFile(path.join(outputDir, "artifact_checks.json"), JSON.stringify({ checks, errors: errors.ndjson }, null, 2));
process.stdout.write(JSON.stringify({ errors: errors.ndjson, previews: outputDir }, null, 2));
