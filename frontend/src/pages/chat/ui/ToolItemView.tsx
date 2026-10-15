import { Check, ChevronRight, LoaderCircle, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import type { Item } from "@/entities/assistant/model/types";
import { useLang } from "@/shared/lib/useLang";

export function ToolItemView({ item, children }: {
  item: Extract<Item, { kind: "tool_call" }>;
  children?: ReactNode;
}) {
  const { pick } = useLang();
  const running = item.status === "running";
  const failed = item.status === "failed";
  return <div className="overflow-hidden rounded-xl border border-background-200 bg-background-50/60">
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center gap-2.5 px-3.5 py-3 text-sm text-foreground-600 [&::-webkit-details-marker]:hidden">
        <Wrench size={15} />
        <span className="min-w-0 flex-1 truncate">{item.name}</span>
        {running ? <LoaderCircle size={14} className="animate-spin text-primary-500" /> : <Check size={14} />}
        <span className={`text-xs ${failed ? "text-red-500" : "text-foreground-400"}`}>
          {running ? pick("进行中", "In progress") : failed ? pick("失败", "Failed") : item.status === "cancelled" ? pick("已停止", "Stopped") : pick("已完成", "Completed")}
        </span>
        <ChevronRight size={14} className="transition-transform group-open:rotate-90" />
      </summary>
      <div className="border-t border-background-200 px-4 py-3 text-xs leading-6">
        <p className="mb-1 font-medium text-foreground-500">{pick("调用参数", "Arguments")}</p>
        <pre className="max-h-60 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-background-100 p-3">{item.argumentsText || "…"}</pre>
        {item.result != null && <>
          <p className="mb-1 mt-3 font-medium text-foreground-500">{pick("执行结果", "Result")}</p>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-background-100 p-3">{JSON.stringify(item.result, null, 2)}</pre>
        </>}
      </div>
    </details>
    {children ? <div className="border-t border-background-200 p-3 sm:p-4">{children}</div> : null}
  </div>;
}

