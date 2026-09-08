import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = process.argv[2];
const outputDir = process.argv[3];
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

const specs = [
  ["Paraphrasing Comparison v3", "A1:T8"],
  ["Preliminary Task Results", "A1:U8"],
  ["No Movement", "A1:S8"],
  ["Relational Movement No Movement", "A1:M8"],
  ["Cross Task Object Chart v2", "A1:M8"],
  ["Familiar Spatial Task Chart", "A1:AE8"],
  ["Matched Manipulation Task Chart", "A1:S8"],
  ["Novel Spatial Task Chart", "A1:M8"],
  ["Emergent Skills Data", "A1:E7"],
  ["Sheet2", "A1:AC13"],
  ["Pi0.5 Robustness", "A1:M12"],
];

await fs.mkdir(outputDir, { recursive: true });
for (const [sheetName, range] of specs) {
  const image = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  const name = sheetName.trim().toLowerCase().replaceAll(/[^a-z0-9]+/g, "_").replaceAll(/^_|_$/g, "");
  await fs.writeFile(path.join(outputDir, `${name}.png`), new Uint8Array(await image.arrayBuffer()));
  process.stdout.write(`Rendered ${sheetName}\n`);
}
