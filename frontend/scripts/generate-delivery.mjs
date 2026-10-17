import { readdir, readFile, writeFile } from "node:fs/promises";
const root = new URL("../../models/riskgnn/dataset_adapters/", import.meta.url);
const presets = [];
for (const item of (await readdir(root, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
  if (!item.isDirectory()) continue;
  let raw;
  try { raw = JSON.parse(await readFile(new URL(`${item.name}/delivery.json`, root), "utf8")); }
  catch (error) { if (error.code === "ENOENT") continue; throw error; }
  for (const [id, preset] of Object.entries(raw.presets)) {
    presets.push({ id, description: preset.description, dataset: preset.dataset, adapter: raw.adapter,
      config: { ...raw.default_config, ...preset.config }, requiredFiles: raw.required_files });
  }
}
const text = JSON.stringify(presets, null, 2) + "\n";
const output = new URL("../src/shared/config/generated/dataset-delivery.json", import.meta.url);
if (process.argv.includes("--check")) {
  if (await readFile(output, "utf8") !== text) throw new Error("数据包预设已漂移，请运行 npm run delivery:generate");
} else await writeFile(output, text);
