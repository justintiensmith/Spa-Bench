import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = process.argv[2];
const outputDir = process.argv[3];

if (!inputPath || !outputDir) {
  throw new Error("Usage: render_reviewed_workbook.mjs INPUT_XLSX OUTPUT_DIR");
}

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
await fs.mkdir(outputDir, { recursive: true });

const specs = [
  ["Failure Summary", "A1:Q21"],
  ["Failure by Task", "A1:G52"],
  ["Failure by Model", "A1:G28"],
  ["Primary Failures", "A1:M24"],
  ["All Classified Failures", "A1:M24"],
  ["Methods", "A1:D27"],
];

for (const [sheetName, range] of specs) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  const name = sheetName.toLowerCase().replaceAll(" ", "_");
  await fs.writeFile(path.join(outputDir, `${name}.png`), new Uint8Array(await preview.arrayBuffer()));
}
