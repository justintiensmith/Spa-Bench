import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = process.argv[2];
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

for (const range of ["Review Queue!A3:K31", "Review Queue!L3:O31"]) {
  const result = await workbook.inspect({
    kind: "table",
    range,
    include: "values,formulas",
    tableMaxRows: 40,
    tableMaxCols: 15,
    maxChars: 30000,
  });
  process.stdout.write(result.ndjson);
}
