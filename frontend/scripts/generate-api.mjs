import { mkdir, readFile, writeFile } from "node:fs/promises";
import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";

const contractUrl = new URL("../../contracts/openapi.json", import.meta.url);
const outputUrl = new URL("../src/shared/api/generated/schema.ts", import.meta.url);
const contract = JSON.parse(await readFile(contractUrl, "utf8"));
const ast = await openapiTS(contract);
const names = Object.keys(contract.components?.schemas ?? {})
  .filter((name) => /^(Request|Response)[A-Z]\w*$/.test(name))
  .sort();

// Export named DTO types in the generated source so callers need no forwarding module.
const namedDtos = names.map((name) => `export type ${name} = components["schemas"]["${name}"];`);
const output = `${COMMENT_HEADER}${astToString(ast).trimEnd()}\n\n${namedDtos.join("\n")}\n`;
await mkdir(new URL("../src/shared/api/generated/", import.meta.url), { recursive: true });
await writeFile(outputUrl, output);
