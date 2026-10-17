import { useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useAiModelConfig } from "@/features/ai-model-config/model/context";
import * as api from "@/features/data-prep/api/scriptApi";
import type { ResponseScriptCatalog, ResponseScriptTask, ResponseScriptTaskSummary } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";

const panel = "rounded-xl border border-background-200 bg-background-100 p-5";
const control = "w-full rounded-lg border border-background-300 bg-background-50 p-3 text-sm disabled:opacity-50";
const button = "rounded-lg border border-background-300 px-4 py-2 text-sm disabled:opacity-40";
const primary = `${button} bg-primary-500 text-white`;
const statusLabels = { queued: "排队等待执行", running: "执行脚本与校验数据中", ready: "校验通过，数据包已就绪", failed: "运行失败，需修复" };
const errorMessages = {
  DATA_PREP_SCRIPT_STALE: "任务或产物版本已变化，请重新加载后重试。",
  DATA_PREP_SCRIPT_BUSY: "该任务已有运行，请等待结束后再执行。",
  DATA_PREP_SCRIPT_INVALID: "脚本语法或目标配置无效，请检查代码与数据集标识。",
  DATA_PREP_RUNNER_UNAVAILABLE: "脚本执行服务暂不可用，请检查 preparation-runner 与 preparation-worker。",
  DATA_PREP_SCRIPT_AGENT_INVALID: "智能体未能完成本次修改，请补充要求后重试。",
  CHAT_OUTPUT_LIMIT: "模型输出达到上限，请在模型设置中提高回答上限。",
  CHAT_NOT_CONFIGURED: "请先配置智能体模型。也可以手动编写和运行脚本。",
  CHAT_AUTH_FAILED: "模型认证失败，请检查智能体设置中的密钥。",
  CHAT_TIMEOUT: "模型响应超时，请稍后重试。",
  CHAT_UNREACHABLE: "暂时无法连接智能体模型，请检查模型设置。",
  DATA_PREP_SIZE_INVALID: "最多16个文件，合计64 MiB。",
  DATA_PREP_CONTENT_INVALID: "文件为空、重复或路径冲突，请重新选择。",
};

function base64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
function saveFile(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function DataPrepPage() {
  const model = useAiModelConfig();
  const [params, setParams] = useSearchParams();
  const id = params.get("task");
  const [catalog, setCatalog] = useState<ResponseScriptCatalog>();
  const [items, setItems] = useState<ResponseScriptTaskSummary[]>([]);
  const [task, setTask] = useState<ResponseScriptTask>();
  const [script, setScript] = useState("");
  const [requirements, setRequirements] = useState("");
  const [message, setMessage] = useState("");
  const [selectedRun, setSelectedRun] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [name, setName] = useState("");
  const [datasetKey, setDatasetKey] = useState("");
  const [version, setVersion] = useState("v1");
  const [preset, setPreset] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const current = task?.id === id ? task : undefined;
  const target = catalog?.items.find(item => item.preset === (current?.preset || preset));
  const dirty = current && (script !== current.script || requirements !== current.requirements);
  const activeRun = current?.runs.some(run => run.status === "queued" || run.status === "running");
  const run = current?.runs.find(item => item.id === selectedRun) || current?.runs[0];

  async function refreshList() { setItems((await api.requestScriptTasks({})).items); }
  useEffect(() => {
    let alive = true;
    api.requestScriptCatalog({}).then(value => {
      if (alive) { setCatalog(value); setPreset(value.items[0]?.preset || ""); }
    }).catch(cause => { if (alive) setError(handleApiError(cause, errorMessages)); });
    api.requestScriptTasks({}).then(value => { if (alive) setItems(value.items); })
      .catch(cause => { if (alive) setError(handleApiError(cause, errorMessages)); });
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    setTask(undefined); setSelectedRun(""); setError(""); setPollError("");
    if (!id) { setScript(""); setRequirements(""); return; }
    let alive = true;
    setLoading(true);
    api.requestScriptTask({ taskId: id }).then(value => { if (alive) setTask(value); })
      .catch(cause => { if (alive) setError(handleApiError(cause, errorMessages)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [id]);
  useEffect(() => {
    if (current) { setScript(current.script); setRequirements(current.requirements); }
    // Polling the same revision must not overwrite unsaved edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.id, current?.revision]);
  useEffect(() => {
    if (!id || !activeRun) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const value = await api.requestScriptTask({ taskId: id });
        if (alive) { setTask(value); setPollError(""); }
      } catch (cause) { if (alive) setPollError(handleApiError(cause, errorMessages)); }
      if (alive) timer = setTimeout(() => void poll(), 2000);
    };
    timer = setTimeout(() => void poll(), 1500);
    return () => { alive = false; clearTimeout(timer); };
  }, [id, activeRun]);

  async function act(operation: () => Promise<void>) {
    setBusy(true); setError("");
    try { await operation(); }
    catch (cause) { setError(handleApiError(cause, errorMessages)); }
    finally { setBusy(false); }
  }
  async function create() {
    if (files.length > 16 || files.reduce((size, file) => size + file.size, 0) > 64 * 1024 ** 2) {
      setError("最多16个文件，合计64 MiB"); return;
    }
    await act(async () => {
      const value = await api.requestCreateScriptTask({ name: name.trim(), preset,
        datasetKey: datasetKey.trim(), datasetVersion: version.trim(), requirements,
        files: await Promise.all(files.map(async file => ({ filename: file.webkitRelativePath ? file.webkitRelativePath.split("/").slice(1).join("/") : file.name, contentBase64: await base64(file) }))),
      });
      setParams({ task: value.id }); setFiles([]); await refreshList();
    });
  }
  async function persist() {
    if (!current) throw new Error("任务尚未加载");
    if (!dirty) return current;
    const value = await api.requestSaveScriptTask({ taskId: current.id, revision: current.revision, script, requirements });
    setTask(value); return value;
  }
  async function switchTask(nextId: string) {
    await act(async () => {
      if (dirty) await persist();
      setParams(nextId ? { task: nextId } : {});
    });
  }
  async function generate(runAfter: boolean) {
    if (!message.trim() || !current) return;
    await act(async () => {
      const saved = await persist();
      try {
        const value = await api.requestGenerateScript({ taskId: saved.id, revision: saved.revision,
          message: message.trim(), connection: model.connection, maxTokens: model.maxTokens, runAfter });
        setTask(value); setMessage(""); setSelectedRun(""); await refreshList();
      } catch (cause) {
        setTask(await api.requestScriptTask({ taskId: saved.id }));
        throw cause;
      }
    });
  }
  async function execute() {
    await act(async () => {
      const saved = await persist();
      setTask(await api.requestRunScript({ taskId: saved.id, revision: saved.revision }));
      setSelectedRun("");
    });
  }
  async function download() {
    if (!current || !run) return;
    await act(async () => {
      const result = await api.requestScriptArtifact({ taskId: current.id, runId: run.id });
      const bytes = Uint8Array.from(atob(result.contentBase64), character => character.charCodeAt(0));
      saveFile(new Blob([bytes], { type: "application/zip" }), result.filename);
    });
  }
  async function deliver() {
    if (!current || !run) return;
    await act(async () => {
      try { await api.requestDeliverScriptArtifact({ taskId: current.id, runId: run.id }); }
      finally { setTask(await api.requestScriptTask({ taskId: current.id })); }
    });
  }

  if (params.has("preparation") || params.get("step") === "delivery")
    return <Navigate replace to={`/data-prep/legacy?${params.toString()}`} />;
  return <div className="mx-auto max-w-7xl space-y-5 p-5 lg:p-8">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><h1 className="text-2xl font-semibold">数据准备工作区</h1><p className="mt-2 text-sm text-foreground-500">让智能体编写转换脚本，在隔离环境中运行与校验，再将数据集交付工作台。</p></div>
      <div className="flex gap-4 text-sm"><Link className="text-primary-500 underline" to="/settings/ai-model">智能体模型设置</Link><Link className="text-foreground-500 underline" to="/data-prep/legacy">历史案例与旧转换流程</Link></div>
    </header>
    <div className="flex flex-wrap gap-3"><select aria-label="数据准备任务" className={`${control} max-w-lg`} value={id || ""} disabled={busy} onChange={event => void switchTask(event.target.value)}><option value="">新建数据准备任务</option>{items.map(item => <option key={item.id} value={item.id}>{item.name} · 脚本版本 {item.revision}</option>)}</select>{id && <button className={button} disabled={busy} onClick={() => void switchTask("")}>新建任务</button>}</div>
    {(error || pollError) && <p role="alert" className="rounded-lg border border-red-500/30 p-3 text-sm text-red-500">{error || pollError}</p>}
    {loading && <p role="status">正在加载任务…</p>}
    {!id && <section className={`${panel} space-y-4`}>
      <h2 className="font-semibold">原始数据与转换目标</h2>
      <div className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-sm">任务名称<input aria-label="任务名称" className={control} value={name} maxLength={128} disabled={busy} onChange={event => setName(event.target.value)} /></label><label className="space-y-2 text-sm">目标模型适配器<select aria-label="目标模型适配器" className={control} value={preset} disabled={busy} onChange={event => setPreset(event.target.value)}>{catalog?.items.map(item => <option key={item.preset} value={item.preset}>{item.adapter.id} / {item.adapter.version} · {item.preset}</option>)}</select></label><label className="space-y-2 text-sm">数据集标识<input aria-label="数据集标识" className={control} value={datasetKey} maxLength={128} disabled={busy} placeholder="例如 my-companies" onChange={event => setDatasetKey(event.target.value)} /></label><label className="space-y-2 text-sm">数据版本前缀（执行时附加脚本版本）<input aria-label="数据版本" className={control} value={version} maxLength={48} disabled={busy} onChange={event => setVersion(event.target.value)} /></label></div>
      <label className="block space-y-2 text-sm">转换要求<textarea aria-label="转换要求" className={control} rows={5} maxLength={12000} value={requirements} disabled={busy} placeholder="说明字段含义、标签定义、缺失处理、关系来源及已有划分；不明确的事项可以先让智能体询问。" onChange={event => setRequirements(event.target.value)} /></label>
      <p className="text-xs text-foreground-500">可上传 CSV、JSON、Parquet 等原始文件。每个任务最多16个文件、合计64 MiB；文件固定保存在该任务中，替换输入请新建任务。</p>
      <div className="flex flex-wrap gap-5 text-sm"><label>添加文件<input aria-label="添加原始文件" className="mt-2 block text-xs" type="file" multiple disabled={busy} onChange={event => { setFiles(previous => [...previous, ...Array.from(event.target.files || [])]); event.target.value = ""; }} /></label><label>添加数据目录<input aria-label="添加数据目录" className="mt-2 block text-xs" type="file" multiple {...{ webkitdirectory: "" }} disabled={busy} onChange={event => { setFiles(previous => [...previous, ...Array.from(event.target.files || [])]); event.target.value = ""; }} /></label></div>
      <ul className="space-y-1 text-xs">{files.map((file, index) => <li key={`${file.name}-${index}`} className="flex gap-3">{file.webkitRelativePath || file.name} · {(file.size / 1024).toFixed(1)} KiB<button disabled={busy} className="text-primary-500 underline" onClick={() => setFiles(previous => previous.filter((_, i) => i !== index))}>移除</button></li>)}</ul>
      <button className={primary} disabled={busy || !name.trim() || !datasetKey.trim() || !version.trim() || !preset || !files.length || !catalog} onClick={() => void create()}>{busy ? "正在保存…" : "创建任务并进入脚本工作区"}</button>
    </section>}
    {current && <>
      <section className={`${panel} space-y-3`}><h2 className="font-semibold">{current.name} <span className="ml-2 text-xs font-normal text-foreground-500">已保存版本 {current.revision}{dirty ? " · 有未保存修改" : ""}</span></h2><p className="text-sm text-foreground-500">{current.datasetKey} / {current.datasetVersion} → {current.preset}</p><details><summary className="cursor-pointer text-sm">原始文件与来源摘要（{current.files.length}）</summary><ul className="mt-2 space-y-2 text-xs">{current.files.map(file => <li key={file.filename} className="break-all">{file.filename} · {(file.size / 1024).toFixed(1)} KiB<br /><span className="font-mono text-foreground-500">{file.sha256}</span></li>)}</ul></details></section>
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.2fr)]">
        <section className={`${panel} space-y-4`}><h2 className="font-semibold">与智能体协作</h2><p className="text-xs text-foreground-500">当前模型：{model.custom ? model.model : model.defaults?.model || "后端默认"}。智能体读取文件预览、目标契约及实际运行日志后提出脚本。</p>
          <label className="block text-sm">任务要求<textarea aria-label="任务要求" className={`${control} mt-2`} rows={5} maxLength={12000} disabled={busy} value={requirements} onChange={event => setRequirements(event.target.value)} /></label>
          <div className="max-h-[480px] space-y-3 overflow-y-auto" aria-label="任务对话">{!current.messages.length && <p className="text-sm text-foreground-500">描述你希望如何转换数据；智能体会先检查输入与目标，必要时询问缺失信息。</p>}{current.messages.map((item, index) => <div key={index} className={`rounded-lg p-3 text-sm ${item.role === "user" ? "bg-primary-500/10" : "bg-background-50"}`}><p className="mb-2 text-xs text-foreground-500">{item.role === "user" ? "你" : "智能体"}</p><p className="whitespace-pre-wrap break-words leading-6">{item.content}</p>{item.toolTrace.length > 0 && <details className="mt-2 text-xs"><summary>工具调用（{item.toolTrace.length}）</summary>{item.toolTrace.map((tool, i) => <p key={i}>{tool}</p>)}</details>}</div>)}</div>
          <textarea aria-label="给智能体的要求" className={control} rows={4} maxLength={12000} disabled={busy} value={message} placeholder="生成转换脚本，或根据本次失败日志修复；保留已有划分和企业ID前导零。" onChange={event => setMessage(event.target.value)} />
          <div className="flex flex-wrap gap-2"><button className={button} disabled={busy || !message.trim()} onClick={() => void generate(false)}>讨论或修改脚本</button><button className={primary} disabled={busy || activeRun || !message.trim()} onClick={() => void generate(true)}>生成并试运行</button>{run?.status === "failed" && <button className={button} disabled={busy} onClick={() => setMessage("请读取最近运行的真实日志和校验错误，解释失败原因，并在不改变已确认业务语义的前提下修复脚本。无法确定时先询问我。")}>用失败日志继续修复</button>}</div>
          {busy && <p role="status" className="text-sm text-foreground-500">正在处理当前请求…</p>}
        </section>
        <div className="min-w-0 space-y-5"><section className={`${panel} space-y-3`}><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">转换脚本 · Python</h2><button className={button} disabled={!script.trim() || busy} onClick={() => saveFile(new Blob([script], { type: "text/x-python" }), "convert.py")}>下载脚本</button></div><p className="text-xs leading-6 text-foreground-500">通过 INPUT_DIR 读取原始文件，通过 OUTPUT_DIR 输出数据集文件。运行环境包含 pandas、numpy、pyarrow、duckdb 和标准库。输入只读、网络关闭；脚本执行限65秒、2 GiB内存。</p><textarea aria-label="Python转换脚本" spellCheck={false} className={`${control} min-h-[420px] font-mono text-xs leading-6`} maxLength={100000} value={script} disabled={busy} onChange={event => setScript(event.target.value)} placeholder="让智能体生成脚本，或在这里编写完整Python代码。" /><div className="flex flex-wrap gap-2"><button className={button} disabled={busy || !dirty} onClick={() => void act(async () => { await persist(); await refreshList(); })}>保存脚本与要求</button><button className={primary} disabled={busy || activeRun || !script.trim()} onClick={() => void execute()}>保存并运行校验</button></div></section>
          <section className={`${panel} space-y-3`}><h2 className="font-semibold">运行、校验与数据包</h2>{!run && <p className="text-sm text-foreground-500">执行后将在这里保留日志、校验报告和数据包。刷新页面可恢复。</p>}{current.runs.length > 0 && <select aria-label="运行历史" className={control} value={run?.id || ""} onChange={event => setSelectedRun(event.target.value)}>{current.runs.map(item => <option key={item.id} value={item.id}>版本 {item.revision} · {statusLabels[item.status]} · {new Date(item.createdAt).toLocaleString()}</option>)}</select>}
            {run && <><p role="status" className="text-sm font-medium">{statusLabels[run.status]}{run.result.datasetVersion ? ` · 数据版本 ${run.result.datasetVersion}` : ""}{run.revision !== current.revision ? " · 历史版本，当前修改尚未应用到该产物" : dirty ? " · 当前编辑尚未保存到本次运行" : ""}</p>{run.error && <p role="alert" className="text-sm text-red-500">{run.error}</p>}<pre aria-label="执行日志" className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-background-50 p-3 font-mono text-xs leading-6">{run.log || (run.status === "queued" ? "等待后台执行器接收任务。" : run.status === "running" ? "正在执行，完成后返回实际日志。" : "脚本没有输出日志。")}</pre>
              <details><summary className="cursor-pointer text-xs">查看本次冻结脚本与执行依据</summary><p className="mt-2 break-all font-mono text-xs">脚本 SHA：{run.scriptSha256}<br />产物 SHA：{run.artifactSha256 || "尚无产物"}<br />环境：{run.result.runtimeImage || "尚未运行"}</p><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{run.script}</pre></details>
              {Object.keys(run.result.validation).length > 0 && <details open={run.status === "ready"}><summary className="cursor-pointer text-sm">模型适配器校验报告</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs">{JSON.stringify(run.result.validation, null, 2)}</pre></details>}
              {run.status === "ready" && <><ul className="max-h-48 overflow-y-auto space-y-1 text-xs">{run.result.files.map(file => <li key={file.path}>{file.path} · {(file.size / 1024).toFixed(1)} KiB</li>)}</ul><div className="flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={() => void download()}>下载标准数据包</button><button className={primary} disabled={busy || run.result.deliveryCompleted} onClick={() => void deliver()}>{run.result.deliveryCompleted ? "已交付工作台" : run.result.deliveryDatasetId ? "重试上传到工作台" : "上传到工作台"}</button></div><p className="text-xs text-foreground-500">交付当前选中运行的产物。工作台会独立重新校验，随后才能创建实验。</p></>}
              {run.result.deliveryCompleted && run.result.deliveryDatasetId && <Link className="block text-sm text-primary-500 underline" to={`/modeling?tab=dataset&dataset=${encodeURIComponent(run.result.deliveryDatasetId)}`}>查看工作台数据集与校验状态 →</Link>}
            </>}
          </section></div>
      </div>
    </>}
    {target && <details className={panel}><summary className="cursor-pointer text-sm font-semibold">目标数据集要求 · {target.adapter.id}</summary><p className="mt-3 text-xs">必需输出：{target.requiredFiles.join("、")}。系统生成契约文件；数据语义和划分仍需明确依据。</p><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap text-xs leading-6">{target.guide}</pre></details>}
  </div>;
}
