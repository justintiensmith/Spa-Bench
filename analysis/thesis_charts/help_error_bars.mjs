import { Workbook } from "@oai/artifact-tool";

const workbook = Workbook.create();
const result = await workbook.help("chart.series error bars custom plus minus values", {
  include: "examples,notes,index",
  maxChars: 16000,
});
process.stdout.write(result.ndjson);
