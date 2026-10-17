import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import presets from "@/shared/config/generated/dataset-delivery.json";
import { handleApiError } from "@/shared/api/http";
import { buildPackage, inspectPackage } from "../lib/package";
import type { PackageSource } from "../lib/package";
import { uploadDatasetPackage } from "../lib/upload";

const control = "rounded-md border border-background-300 bg-background-50 p-2 text-sm disabled:opacity-50";
const button = `${control} px-4`;

export function DatasetDeliveryPanel({ sourcePreparationId }: { sourcePreparationId?: string }) {
  const sequence = useRef(0);
  const [presetId, setPresetId] = useState(presets[0].id);
  const [version, setVersion] = useState("");
  const [sources, setSources] = useState<PackageSource[]>([]);
  const [artifact, setArtifact] = useState<File>();
  const [entries, setEntries] = useState<{ filename: string; size: number }[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [progress, setProgress] = useState(0);
  const [datasetId, setDatasetId] = useState("");
  const [attachSource, setAttachSource] = useState(false);
  const preset = presets.find(item => item.id === presetId)!;
  function resetArtifact() { sequence.current++; setArtifact(undefined); setEntries([]); setDatasetId(""); setError(""); setNotice(""); }
  async function chooseZip(file?: File) {
    resetArtifact();
    if (!file) return;
    const current = sequence.current;
    setBusy(true);
    try {
      const preview = await inspectPackage(file);
      if (current !== sequence.current) return;
      setArtifact(file); setEntries(preview); setName(file.name.replace(/\.zip$/i, ""));
      setNotice("已检查文件清单，上传后由工作台独立校验数据内容。");
    } catch (cause) { if (current === sequence.current) setError(handleApiError(cause)); }
    finally { setBusy(false); }
  }
  async function generate() {
    resetArtifact(); setBusy(true);
    try {
      const result = await buildPackage(preset, version, sources);
      const filename = `${preset.id}-${version.trim().replace(/[^a-zA-Z0-9_.-]/g, "_")}.zip`;
      const file = new File([result.blob], filename, { type: "application/zip" });
      setArtifact(file); setEntries(await inspectPackage(file)); setName(`${preset.dataset.name} · ${version.trim()}`.slice(0, 128));
      setNotice(`标准包已生成，仅完成打包检查；训练可用性以工作台校验为准。${result.sourceContractIgnored ? "源目录中的旧根契约已在包内重新生成，原文件未修改。" : ""}`);
    } catch (cause) { setError(handleApiError(cause)); }
    finally { setBusy(false); }
  }
  function download() {
    if (!artifact) return;
    const url = URL.createObjectURL(artifact);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = artifact.name; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function upload() {
    if (!artifact || busy || !name.trim() || datasetId) return;
    setBusy(true); setError(""); setProgress(0);
    try {
      const id = await uploadDatasetPackage(artifact, name.trim(), {
        sourcePreparationId: attachSource ? sourcePreparationId : undefined, progress: setProgress,
      });
      setDatasetId(id);
    } catch (cause) { setError(handleApiError(cause)); }
    finally { setBusy(false); }
  }
  return <section aria-label="标准训练包交付" className="space-y-4 rounded-xl border border-background-200 bg-background-100 p-5">
    <div><h2 className="font-semibold">生成并交付工作台数据包</h2><p className="mt-2 text-sm leading-6 text-foreground-500">将已按模型适配器要求准备的文件生成标准 ZIP，下载后自行上传，或在这里直接上传到工作台。智能体负责辅助核对字段和规则；缺失的标签语义、关系证据和独立划分仍需补齐。</p></div>
    <fieldset disabled={busy} className="space-y-3 disabled:opacity-60">
      <label className="block text-sm">适配器预设<select aria-label="适配器预设" className={`${control} ml-3`} value={presetId} onChange={event => { resetArtifact(); setPresetId(event.target.value); }}>
        {presets.map(item => <option key={item.id} value={item.id}>{item.dataset.name} · {item.adapter.id} / {item.adapter.version}</option>)}
      </select></label>
      <p className="text-xs text-foreground-500">必需文件：{preset.requiredFiles.join("、")}。保留目录结构；不会把任意 CSV 自动转换成这些文件，也不会生成训练划分。</p>
      <label className="block text-sm">数据版本<input aria-label="数据版本" className={`${control} ml-3`} maxLength={64} value={version} placeholder="例如 2026-10-17-v1" onChange={event => { resetArtifact(); setVersion(event.target.value); }} /></label>
      <label className="block text-sm">选择已适配的数据目录<input aria-label="选择已适配的数据目录" type="file" multiple {...{ webkitdirectory: "" }} className="mt-2 block text-xs" onChange={event => {
        resetArtifact();
        const files = Array.from(event.target.files ?? []);
        setSources(files.map(file => ({ file, path: (file.webkitRelativePath || file.name).split("/").slice(file.webkitRelativePath ? 1 : 0).join("/") })));
        event.target.value = "";
      }} /></label>
      {sources.length > 0 && <p className="text-xs">已选择 {sources.length} 个文件 · {(sources.reduce((total, source) => total + source.file.size, 0) / 1024 ** 2).toFixed(1)} MiB</p>}
      <p className="text-xs text-foreground-500">浏览器生成包最多512 MiB（含契约），最多128个文件；更大文件请使用独立打包命令并选择已有 ZIP。预设使用适配器声明的默认参数，实验参数可在工作台调整。</p>
      <button className={button} disabled={!sources.length || !version.trim()} onClick={() => void generate()}>生成标准训练包</button>
      <div className="border-t border-background-200 pt-3"><label className="block text-sm">或选择已有标准 ZIP<input aria-label="选择已有标准ZIP" className="mt-2 block text-xs" type="file" accept=".zip,application/zip" onChange={event => { void chooseZip(event.target.files?.[0]); event.target.value = ""; }} /></label></div>
    </fieldset>
    {busy && <p role="status" className="text-sm">正在处理… {progress > 0 ? `上传 ${progress}%` : ""}</p>}
    {notice && <p role="status" className="text-sm text-foreground-500">{notice}</p>}
    {artifact && <div className="space-y-3 border-t border-background-200 pt-3">
      <p className="text-sm">{artifact.name} · {(artifact.size / 1024 ** 2).toFixed(1)} MiB</p>
      <details><summary className="cursor-pointer text-sm">查看包内文件（{entries.length}）</summary><ul className="max-h-48 overflow-auto text-xs">{entries.map(entry => <li key={entry.filename} className="py-1">{entry.filename} · {(entry.size / 1024).toFixed(1)} KiB</li>)}</ul></details>
      <label className="block text-sm">工作台数据集名称<input aria-label="工作台数据集名称" className={`${control} ml-3`} maxLength={128} value={name} disabled={busy || !!datasetId} onChange={event => setName(event.target.value)} /></label>
      {sourcePreparationId && <label className="flex gap-2 text-xs"><input type="checkbox" disabled={busy || !!datasetId} checked={attachSource} onChange={event => setAttachSource(event.target.checked)} />此包由当前已确认案例派生，上传时封存该案例的来源摘要和映射。</label>}
      <div className="flex flex-wrap gap-3"><button className={button} disabled={busy} onClick={download}>下载标准训练包</button><button className={`${button} bg-primary-500 text-white`} disabled={busy || !name.trim() || !!datasetId} onClick={() => void upload()}>{datasetId ? "已上传" : "直接上传到工作台"}</button></div>
    </div>}
    {datasetId && <p role="status" className="text-sm">上传完成，等待工作台校验。<Link className="ml-2 text-primary-500 underline" to={`/modeling?tab=dataset&dataset=${encodeURIComponent(datasetId)}`}>查看数据集与校验状态 →</Link></p>}
    {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
  </section>;
}
