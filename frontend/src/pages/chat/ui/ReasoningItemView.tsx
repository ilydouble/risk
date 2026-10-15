import { Brain, Check, ChevronRight, LoaderCircle, Square, X } from "lucide-react";
import { useId, useState } from "react";
import type { Item } from "@/entities/assistant/model/types";
import { useLang } from "@/shared/lib/useLang";
import { MessageMarkdown } from "./MessageMarkdown";

export function ReasoningItemView({ item }: { item: Extract<Item, { kind: "reasoning" }> }) {
  const { pick } = useLang();
  const contentId = useId();
  const [expandedByUser, setExpandedByUser] = useState<boolean | null>(null);
  const running = item.status === "running";
  // Follow execution until the user chooses; later deltas must not undo that choice.
  const expanded = expandedByUser ?? running;
  const label = running ? pick("正在思考", "Thinking")
    : item.status === "failed" ? pick("思考中断", "Reasoning failed")
    : item.status === "cancelled" ? pick("已停止思考", "Reasoning stopped")
    : pick("思考完成", "Reasoning complete");
  const StatusIcon = running ? LoaderCircle : item.status === "failed" ? X
    : item.status === "cancelled" ? Square : Check;

  return <section aria-label={pick("推理过程", "Reasoning")} className="min-w-0 rounded-xl bg-background-50/60 text-foreground-500">
    <button type="button" aria-expanded={expanded} aria-controls={contentId}
      onClick={() => setExpandedByUser(!expanded)}
      className="flex w-full items-center gap-2.5 rounded-xl px-3.5 py-3 text-left text-sm transition-colors hover:bg-background-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
      <Brain size={16} aria-hidden="true" className="shrink-0" />
      <span className="flex-1" aria-live="polite">{label}</span>
      <StatusIcon size={14} aria-hidden="true" className={running ? "animate-spin motion-reduce:animate-none" : ""} />
      <ChevronRight size={14} aria-hidden="true" className={`transition-transform motion-reduce:transition-none ${expanded ? "rotate-90" : ""}`} />
    </button>
    <div id={contentId} hidden={!expanded} className="px-4 pb-4">
      <div className="chat-markdown max-h-80 overflow-y-auto break-words border-l-2 border-background-200 pl-4 text-sm leading-7">
        {item.text ? <MessageMarkdown text={item.text} /> : <p>{pick("等待推理内容…", "Waiting for reasoning…")}</p>}
      </div>
    </div>
  </section>;
}
