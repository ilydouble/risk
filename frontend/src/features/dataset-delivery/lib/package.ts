import { BlobReader, BlobWriter, TextReader, ZipReader, ZipWriter } from "@zip.js/zip.js";

export const CONTRACT = "risk_dataset_contract.json";
export type DeliveryPreset = {
  id: string;
  description: string;
  dataset: { id: string; name?: string; description?: string };
  adapter: { id: string; version: string };
  config: Record<string, unknown>;
  requiredFiles: string[];
};
export type PackageSource = { path: string; file: Blob };
const MAX_UPLOAD = 512 * 1024 * 1024;

function safePath(path: string) {
  if (!path || /[\\:]/.test(path) || path.split("/").some(part => !part || part === "." || part === ".."))
    throw new Error(`文件路径无效：${path}`);
}

export function preparePackage(preset: DeliveryPreset, version: string, sources: PackageSource[]) {
  if (!version.trim() || version.length > 64) throw new Error("请填写1–64字符的数据版本");
  const paths = new Set<string>();
  let total = 0;
  const files = sources.filter(source => {
    safePath(source.path);
    if (paths.has(source.path)) throw new Error(`文件重复：${source.path}`);
    paths.add(source.path);
    if (source.path === CONTRACT) return false;
    if (source.path.split("/").at(-1) === CONTRACT) throw new Error("不能包含嵌套的数据包契约，请选择单一数据根目录");
    total += source.file.size;
    if (source.file.size > 1024 ** 3 || total > 2 * 1024 ** 3) throw new Error("文件或总大小超出工作台限制");
    return true;
  });
  if (files.length + 1 > 128) throw new Error("数据包最多128个文件（含契约）");
  if (total > MAX_UPLOAD - 1024 * 1024) throw new Error("浏览器打包文件合计需小于511 MiB；更大数据请使用独立打包命令");
  const missing = preset.requiredFiles.filter(path => !paths.has(path));
  if (missing.length) throw new Error(`缺少适配器必需文件：${missing.join("、")}`);
  return { files, contract: { contract_version: 1, dataset: { ...preset.dataset, version: version.trim() },
    adapter: { ...preset.adapter, config: preset.config } }, sourceContractIgnored: paths.has(CONTRACT) };
}

export async function inspectPackage(file: Blob) {
  if (!file.size || file.size > MAX_UPLOAD) throw new Error("ZIP大小必须为1字节至512 MiB");
  const reader = new ZipReader(new BlobReader(file));
  try {
    const entries = await reader.getEntries();
    if (entries.length > 128) throw new Error("ZIP最多128个成员");
    const paths = new Set<string>();
    let total = 0;
    for (const entry of entries) {
      const path = entry.directory ? entry.filename.replace(/\/$/, "") : entry.filename;
      safePath(path);
      if (paths.has(path) || entry.encrypted) throw new Error("ZIP包含重复路径或加密文件");
      paths.add(path);
      total += entry.uncompressedSize;
      if (entry.uncompressedSize > 1024 ** 3 || total > 2 * 1024 ** 3 || entry.uncompressedSize > Math.max(1, entry.compressedSize) * 200)
        throw new Error("ZIP解压资源超出工作台限制");
    }
    if (entries.filter(entry => !entry.directory && /^(?:[^/]+\/)?risk_dataset_contract\.json$/.test(entry.filename)).length !== 1)
      throw new Error("ZIP必须包含一份根目录或单层目录中的 risk_dataset_contract.json");
    if (entries.filter(entry => entry.filename.split("/").at(-1) === CONTRACT).length !== 1)
      throw new Error("ZIP不能包含多份契约");
    return entries.filter(entry => !entry.directory).map(entry => ({ filename: entry.filename, size: entry.uncompressedSize }));
  } finally { await reader.close(); }
}

export async function buildPackage(preset: DeliveryPreset, version: string, sources: PackageSource[]) {
  const prepared = preparePackage(preset, version, sources);
  const writer = new ZipWriter(new BlobWriter("application/zip"));
  let blob: Blob;
  try {
    for (const source of prepared.files) {
      // Stored entries avoid generating archives rejected for extreme compression ratios.
      await writer.add(source.path, new BlobReader(source.file), { level: 0 });
    }
    await writer.add(CONTRACT, new TextReader(JSON.stringify(prepared.contract)), { level: 0 });
  } finally { blob = await writer.close(); }
  await inspectPackage(blob);
  return { blob, ...prepared };
}
