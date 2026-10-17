import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { BlobReader, BlobWriter, ZipReader } from "@zip.js/zip.js";
import { buildPackage, inspectPackage, preparePackage, CONTRACT } from "../src/features/dataset-delivery/lib/package.ts";

const presets = JSON.parse(await readFile(new URL("../src/shared/config/generated/dataset-delivery.json", import.meta.url)));
const preset = presets.find(item => item.id === "smesd");
const sources = preset.requiredFiles.map(path => ({ path, file: new Blob(["{\"nodes\":[]}"]) }));

test("browser delivery presets track authoritative adapter declarations", () => {
  execFileSync(process.execPath, ["scripts/generate-delivery.mjs", "--check"], { cwd: new URL("../", import.meta.url) });
});

test("builds a standalone contract ZIP while preserving source bytes and independent splits", async () => {
  const result = await buildPackage(preset, "v1", sources);
  assert.equal(result.contract.dataset.version, "v1");
  assert.deepEqual(result.contract.adapter.config, preset.config);
  const reader = new ZipReader(new BlobReader(result.blob));
  try {
    const entries = await reader.getEntries();
    for (const source of sources) {
      const entry = entries.find(item => item.filename === source.path);
      assert.equal(await (await entry.getData(new BlobWriter())).text(), await source.file.text());
    }
    assert.equal(entries.filter(item => item.filename === CONTRACT).length, 1);
    const contract = JSON.parse(await (await entries.find(item => item.filename === CONTRACT).getData(new BlobWriter())).text());
    assert.deepEqual(contract, result.contract);
  } finally { await reader.close(); }
  assert.equal((await inspectPackage(result.blob)).length, sources.length + 1);
});

test("rejects missing files, ambiguous contracts, traversal and duplicate paths", () => {
  assert.throws(() => preparePackage(preset, "v1", sources.slice(1)), /train.json/);
  for (const path of ["../bad", "/absolute", "a\\b", "a/./b", "a//b", `nested/${CONTRACT}`])
    assert.throws(() => preparePackage(preset, "v1", [...sources, { path, file: new Blob() }]));
  assert.throws(() => preparePackage(preset, "v1", [...sources, sources[0]]), /重复/);
  assert.throws(() => preparePackage(preset, " ", sources), /版本/);
});

test("replaces only the root source contract without modifying the source", async () => {
  const old = new Blob(["old contract"]);
  const result = await buildPackage(preset, "v2", [...sources, { path: CONTRACT, file: old }]);
  assert.equal(result.sourceContractIgnored, true);
  assert.equal(await old.text(), "old contract");
  assert.equal(result.contract.dataset.version, "v2");
});

test("rejects oversized sources before compression and rejects a ZIP without a contract", async () => {
  assert.throws(() => preparePackage(preset, "v1", [...sources, { path: "large.bin", file: { size: 512 * 1024 ** 2 } }]), /511 MiB/);
  const { ZipWriter } = await import("@zip.js/zip.js");
  const writer = new ZipWriter(new BlobWriter());
  await writer.add("train.json", new BlobReader(new Blob(["{}"])), { level: 0 });
  await assert.rejects(inspectPackage(await writer.close()), /risk_dataset_contract/);
});
