import { Brain, Check, LoaderCircle, Square, X } from "lucide-react";
import type { Item } from "@/entities/assistant/model/types";
import { useLang } from "@/shared/lib/useLang";
import { MessageMarkdown } from "./MessageMarkdown";

export function ReasoningItemView({ item }: { item: Extract<Item, { kind: "reasoning" }> }) {
  const { pick } = useLang();
  const running = item.status === "running";
  const label = running ? pick("正在思考", "Thinking")
    : item.status === "failed" ? pick("思考中断", "Reasoning failed")
    : item.status === "cancelled" ? pick("已停止思考", "Reasoning stopped")
    : pick("思考完成", "Reasoning complete");
  const StatusIcon = running ? LoaderCircle : item.status === "failed" ? X
    : item.status === "cancelled" ? Square : Check;

  return <section aria-label={pick("推理过程", "Reasoning")} className="min-w-0 rounded-xl bg-background-50/60 text-foreground-500">
    <div className="flex items-center gap-2.5 px-3.5 py-3 text-sm">
      <Brain size={16} aria-hidden="true" className="shrink-0" />
      <span className="flex-1" aria-live="polite">{label}</span>
      <StatusIcon size={14} aria-hidden="true" className={running ? "animate-spin motion-reduce:animate-none" : ""} />
    </div>
    <div className="px-4 pb-4">
      <div className="chat-markdown max-h-80 overflow-y-auto break-words border-l-2 border-background-200 pl-4 text-sm leading-7">
        {item.text ? <MessageMarkdown text={item.text} /> : <p>{pick("等待推理内容…", "Waiting for reasoning…")}</p>}
      </div>
    </div>
  </section>;
}
