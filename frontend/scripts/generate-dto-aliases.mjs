import { readFile, writeFile } from "node:fs/promises";

const contract = JSON.parse(await readFile(new URL("../../contracts/openapi.json", import.meta.url)));
const names = Object.keys(contract.components.schemas)
  .filter((name) => /^(Request|Response)[A-Z]/.test(name))
  .sort();
const output = [
  "// Generated from contracts/openapi.json. Do not edit by hand.",
  'import type { components } from "./schema";',
  "",
  ...names.map((name) => `export type ${name} = components["schemas"]["${name}"];`),
  "",
].join("\n");
await writeFile(new URL("../src/shared/api/dto.ts", import.meta.url), output);
