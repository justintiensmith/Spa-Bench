import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = process.argv[2] ?? "/Users/justintiensmith/Documents/lerobot/outputs/01a0678e-4e7e-7a31-b018-7fba72ab9fe5/Spa_Bench_Manifest_and_Failure_Analysis_Reviewed.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

for (const [sheetId, range] of [
  ["Read Me", "A11:B20"],
  ["Failure Summary", "A4:F17"],
  ["Failure by Task", "A4:G12"],
  ["Failure by Model", "A4:G12"],
  ["All Failure Summary", "A4:F17"],
  ["Failure by Condition", "A4:G16"],
  ["Review Queue", "A1:O31"],
  ["All Classified Failures", "A1:M8"],
  ["Methods", "A3:B30"],
  ["Task Names", "A3:C9"],
]) {
  const result = await workbook.inspect({
    kind: "table",
    sheetId,
    range,
    include: "values,formulas",
    tableMaxRows: 20,
    tableMaxCols: 10,
    maxChars: 10000,
  });
  process.stdout.write(result.ndjson);
}

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "post-export formula error scan",
});
process.stdout.write(errors.ndjson);
