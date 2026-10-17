import { Bot, ChevronRight, Clock3, LoaderCircle } from "lucide-react";
import { useId, useState } from "react";
import type { Turn } from "@/entities/assistant/model/types";
import { useLang } from "@/shared/lib/useLang";
import { MessageMarkdown } from "./MessageMarkdown";
import { TurnProcess } from "./TurnProcess";
import { TurnDuration } from "./TurnDuration";
import { segmentTurnItems } from "../model/timeline";

export function TurnTimeline({ turn }: { turn: Turn }) {
  const { pick } = useLang();
  const userItems = turn.items.filter(item => item.kind === "user_message");
  const blocks = segmentTurnItems(turn.items).filter(
    block => block.kind === "process" || block.item.kind !== "user_message",
  );
  const detailsId = useId();
  const lastAnswer = [...turn.items].reverse().find(item => item.kind === "agent_message");
  // Choose only when mounting this Turn: live completion must not collapse the conversation.
  // Historical turns without an answer remain inspectable.
  const [expanded, setExpanded] = useState(() => turn.status === "running" || !lastAnswer);
  return <section aria-label={pick("对话轮次", "Conversation turn")} className="space-y-5">
    {userItems.map(item => <div key={item.id}
      className="ml-auto max-w-[88%] rounded-2xl rounded-tr-md bg-background-200/70 px-5 py-3.5">
      <p className="mb-1 text-xs text-foreground-400">{pick("你", "You")}</p>
      <p className="whitespace-pre-wrap break-words text-sm leading-7">{item.text.split("\n\n【当前案例上下文】只处理 preparation:")[0]}</p>
      {item.text.includes("\n\n【当前案例上下文】只处理 preparation:") && <p className="mt-2 text-xs text-foreground-400">{pick("已关联数据准备案例", "Data preparation case attached")}</p>}
    </div>)}
    <div>
      <button type="button" aria-expanded={expanded} aria-controls={detailsId}
        onClick={() => setExpanded(value => !value)}
        title={pick("展开或收起本轮对话", "Expand or collapse this turn")}
        className="flex items-center gap-2 rounded-lg px-2 py-2 text-sm text-foreground-400 hover:bg-background-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
        <TurnDuration turn={turn} />
        <ChevronRight size={14} aria-hidden="true" className={`transition-transform motion-reduce:transition-none ${expanded ? "rotate-90" : ""}`} />
      </button>
      <hr className="mt-2 border-background-200" />
    </div>
    <div id={detailsId} className="space-y-5">
    {blocks.map((block, index) => <div key={block.id}
      hidden={!expanded && !(block.kind === "message" && block.id === lastAnswer?.id)}>
      {block.kind === "process" ?
      <TurnProcess key={block.id} items={block.items}
        status={index === blocks.length - 1 ? turn.status : "completed"} />
      :
      <div key={block.id} className="relative">
        <div aria-hidden="true" className="absolute -left-10 top-1 flex h-7 w-7 items-center justify-center rounded-lg bg-primary-500/10 text-primary-500"><Bot size={17} /></div>
        <div className="chat-markdown min-w-0 break-words pt-1 text-sm leading-7">
          <MessageMarkdown text={block.item.text} />
        </div>
      </div>}
    </div>)}
    </div>
    {turn.status === "running" && <div role="status" className="flex items-center gap-2 text-xs text-foreground-400">
      <LoaderCircle size={14} className="animate-spin" />{pick("Agent 正在执行", "Agent is working")}
    </div>}
    {turn.status !== "running" && <div className="flex flex-wrap items-center gap-2 text-xs text-foreground-400">
      <Clock3 size={12} />
      <span>{turn.status === "completed" ? pick("完成", "Completed") : turn.status === "cancelled" ? pick("已停止", "Stopped") : turn.status === "interrupted" ? pick("执行已中断，可重新发送", "Interrupted — send again to retry") : pick("执行失败，请检查模型设置后重试", "Failed — check model settings and retry")}</span>
      <span>· {turn.model}</span>
      <span title={turn.requestId}>{pick("请求", "Request")} {turn.requestId.slice(0, 8)}</span>
    </div>}
  </section>;
}
