import { ChevronRight, LoaderCircle } from "lucide-react";
import { useId, useState } from "react";
import type { Turn } from "@/entities/assistant/model/types";
import { GraphResultCard } from "@/features/company-graph/ui/GraphResultCard";
import { useLang } from "@/shared/lib/useLang";

import type { ProcessItem } from "../model/timeline";
import { ReasoningItemView } from "./ReasoningItemView";
import { ToolItemView } from "./ToolItemView";

export function TurnProcess({ items, status }: {
  items: ProcessItem[];
  status: Turn["status"];
}) {
  const { pick } = useLang();
  const running = status === "running";
  const contentId = useId();
  const [expandedByUser, setExpandedByUser] = useState<boolean | null>(null);
  const expanded = expandedByUser ?? running;
  const toolCount = items.filter(item => item.kind === "tool_call").length;
  const reasoningCount = items.length - toolCount;
  const label = running ? pick("执行中", "Working")
    : status === "failed" ? pick("执行失败", "Execution failed")
    : status === "cancelled" ? pick("执行已停止", "Execution stopped")
    : status === "interrupted" ? pick("执行已中断", "Execution interrupted")
    : pick("执行过程", "Execution details");

  return <div className="min-w-0 sm:ml-10">
    <button type="button" aria-expanded={expanded} aria-controls={contentId}
      onClick={() => setExpandedByUser(!expanded)}
      className="flex max-w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-lg px-2 py-2 text-left text-sm text-foreground-500 transition-colors hover:bg-background-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
      {running && <LoaderCircle size={14} aria-hidden="true" className="animate-spin motion-reduce:animate-none" />}
      <span aria-live="polite">{label}</span>
      <span className="text-xs text-foreground-400">
        {[
          reasoningCount > 0 ? pick(`${reasoningCount} 段推理`, `${reasoningCount} reasoning ${reasoningCount === 1 ? "step" : "steps"}`) : "",
          toolCount > 0 ? pick(`${toolCount} 次工具调用`, `${toolCount} tool ${toolCount === 1 ? "call" : "calls"}`) : "",
        ].filter(Boolean).join(" · ")}
      </span>
      <ChevronRight size={14} aria-hidden="true" className={`shrink-0 transition-transform motion-reduce:transition-none ${expanded ? "rotate-90" : ""}`} />
    </button>
    <div id={contentId} hidden={!expanded} className="pt-2">
      <div className="space-y-3 border-l border-background-200 pl-3 sm:pl-4">
        {items.map(item => item.kind === "reasoning"
          ? <ReasoningItemView key={item.id} item={item} />
          : <ToolItemView key={item.id} item={item}>
            {item.status === "completed" && item.graph && <GraphResultCard reference={item.graph} />}
          </ToolItemView>)}
      </div>
    </div>
  </div>;
}
