import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import type { ResponsePreparationDeletion } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { requestDeletePreparation, requestPreviewPreparationDeletion } from "../api/dataPrepApi";

const DELETE_ERRORS = {
  DATA_PREP_NOT_FOUND: "案例已删除或无权访问，请返回数据准备刷新列表。",
  DATA_PREP_DELETE_STALE: "案例或关联数据已变化，请重新核对删除范围并确认。",
  DATA_PREP_DELETE_BLOCKED: "存在关联依赖，不能删除。请重新核对范围查看原因。",
};

export function PreparationDeleteButton({ preparationId, disabled, onDeleted }: {
  preparationId: string;
  disabled?: boolean;
  onDeleted: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [scope, setScope] = useState<ResponsePreparationDeletion>();
  const [loading, setLoading] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState("");
  async function preview() {
    setLoading(true); setError(""); setScope(undefined); setChecked(false);
    try { setScope(await requestPreviewPreparationDeletion({ preparationId })); }
    catch (cause) { setError(handleApiError(cause, DELETE_ERRORS)); }
    finally { setLoading(false); }
  }
  async function remove() {
    if (!scope || scope.preparationId !== preparationId || scope.blockedReason || !checked || removing) return;
    setRemoving(true); setError("");
    try {
      const result = await requestDeletePreparation({ preparationId, revision: scope.revision, confirm: true });
      if (result.deleted) { setOpen(false); onDeleted(); }
    } catch (cause) {
      setChecked(false); setScope(undefined); setError(handleApiError(cause, DELETE_ERRORS));
    } finally { setRemoving(false); }
  }
  return <Dialog.Root open={open} onOpenChange={value => { if (!removing) setOpen(value); }}>
    <Dialog.Trigger asChild><button type="button" disabled={disabled} onClick={() => void preview()} className="text-sm text-red-600 underline disabled:opacity-40">删除案例及关联数据</button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
      <Dialog.Content onEscapeKeyDown={event => { if (removing) event.preventDefault(); }} onPointerDownOutside={event => { if (removing) event.preventDefault(); }} className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[min(560px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 space-y-4 overflow-auto rounded-xl border border-background-300 bg-background-100 p-6 shadow-xl">
        <Dialog.Title className="text-lg font-semibold">删除案例及关联数据</Dialog.Title>
        <Dialog.Description className="text-sm leading-6 text-foreground-500">删除仅针对当前账号的这一个案例版本，操作无法撤销。共享演示数据、仓库样例文件和助手历史对话保留。</Dialog.Description>
        {loading && <p role="status" className="text-sm">正在核对关联数据…</p>}
        {scope && <div className="space-y-3 text-sm"><p className="break-all font-medium">{scope.filename}</p><ul className="list-disc space-y-1 pl-5"><li>原始上传文件 {scope.counts.files} 个、分析报告 {scope.counts.reports} 份</li><li>字段映射、转换规则及 {scope.counts.tasks} 次试运行/转换记录</li><li>已导入数据集 {scope.counts.datasets} 个、企业 {scope.counts.records.company ?? 0} 家、关系 {scope.counts.records.edge ?? 0} 条、群组 {scope.counts.records.hyperedge ?? 0} 组</li><li>关联预测记录 {scope.counts.predictions} 条</li></ul>{scope.blockedReason ? <p role="alert" className="rounded-lg bg-amber-500/10 p-3 text-amber-700">{scope.blockedReason}</p> : <label className="flex items-start gap-2 leading-6"><input type="checkbox" checked={checked} disabled={removing} onChange={event => setChecked(event.target.checked)} />我已核对删除范围，确认永久删除上述案例及关联数据。</label>}</div>}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        {!scope && !loading && <button type="button" onClick={() => void preview()} className="text-sm text-primary-500 underline">重新核对删除范围</button>}
        <div className="flex justify-end gap-3"><Dialog.Close asChild><button type="button" disabled={removing} className="rounded-lg border border-background-300 px-4 py-2 text-sm">取消</button></Dialog.Close><button type="button" disabled={!scope || Boolean(scope.blockedReason) || !checked || loading || removing} onClick={() => void remove()} className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-40">{removing ? "正在删除…" : "确认永久删除"}</button></div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
