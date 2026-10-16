import { Bot, Brain, Check, ChevronRight, Clock3, LoaderCircle, Wrench } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Item, Turn } from "@/entities/assistant/model/types";
import { useLang } from "@/shared/lib/useLang";

function ProcessItem({ item }: { item: Item }) {
  const { pick } = useLang();
  if (item.kind !== "tool_call" && item.kind !== "reasoning") return null;
  const running = item.status === "running";
  const failed = item.status === "failed";
  return <details className="group rounded-xl border border-background-200 bg-background-50/60">
    <summary className="flex cursor-pointer list-none items-center gap-2.5 px-3.5 py-3 text-sm text-foreground-600 [&::-webkit-details-marker]:hidden">
      {item.kind === "tool_call" ? <Wrench size={15} /> : <Brain size={15} />}
      <span className="min-w-0 flex-1 truncate">{item.kind === "tool_call" ? item.name : pick("推理过程", "Reasoning")}</span>
      {running ? <LoaderCircle size={14} className="animate-spin text-primary-500" /> : <Check size={14} />}
      <span className={`text-xs ${failed ? "text-red-500" : "text-foreground-400"}`}>
        {running ? pick("进行中", "In progress") : failed ? pick("失败", "Failed") : item.status === "cancelled" ? pick("已停止", "Stopped") : pick("已完成", "Completed")}
      </span>
      <ChevronRight size={14} className="transition-transform group-open:rotate-90" />
    </summary>
    <div className="border-t border-background-200 px-4 py-3 text-xs leading-6">
      {item.kind !== "tool_call" ? <p className="whitespace-pre-wrap break-words text-foreground-500">{item.text}</p> : <>
        <p className="mb-1 font-medium text-foreground-500">{pick("调用参数", "Arguments")}</p>
        <pre className="max-h-60 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-background-100 p-3">{item.argumentsText || "…"}</pre>
        {item.result != null && <>
          <p className="mb-1 mt-3 font-medium text-foreground-500">{pick("执行结果", "Result")}</p>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-background-100 p-3">{JSON.stringify(item.result, null, 2)}</pre>
        </>}
      </>}
    </div>
  </details>;
}

export function TurnTimeline({ turn }: { turn: Turn }) {
  const { pick } = useLang();
  return <section aria-label={pick("对话轮次", "Conversation turn")} className="space-y-5">
    {turn.items.map(item => item.kind === "user_message" ?
      <div key={item.id} className="ml-auto max-w-[88%] rounded-2xl rounded-tr-md bg-background-200/70 px-5 py-3.5">
        <p className="mb-1 text-xs text-foreground-400">{pick("你", "You")}</p>
        <p className="whitespace-pre-wrap break-words text-sm leading-7">{item.text.split("\n\n【当前案例上下文】只处理 preparation:")[0]}</p>
        {item.text.includes("\n\n【当前案例上下文】只处理 preparation:") && <p className="mt-2 text-xs text-foreground-400">{pick("已关联数据准备案例", "Data preparation case attached")}</p>}
      </div> : item.kind === "agent_message" ?
        <div key={item.id} className="flex gap-3">
          <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary-500/10 text-primary-500"><Bot size={17} /></div>
          <div className="chat-markdown min-w-0 flex-1 break-words pt-1 text-sm leading-7">
            <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{
              a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
              img: ({ alt }) => <span>[{alt || pick("图片", "Image")}]</span>,
              table: ({ children }) => <div className="overflow-x-auto"><table>{children}</table></div>,
            }}>{item.text}</ReactMarkdown>
          </div>
        </div> : <div key={item.id} className="sm:ml-10"><ProcessItem item={item} /></div>)}
    {turn.status === "running" && <div role="status" className="flex items-center gap-2 text-xs text-foreground-400 sm:ml-10">
      <LoaderCircle size={14} className="animate-spin" />{pick("Agent 正在执行", "Agent is working")}
    </div>}
    {turn.status !== "running" && <div className="flex flex-wrap items-center gap-2 text-xs text-foreground-400 sm:ml-10">
      <Clock3 size={12} />
      <span>{turn.status === "completed" ? pick("完成", "Completed") : turn.status === "cancelled" ? pick("已停止", "Stopped") : turn.status === "interrupted" ? pick("执行已中断，可重新发送", "Interrupted — send again to retry") : pick("执行失败，请检查模型设置后重试", "Failed — check model settings and retry")}</span>
      <span>· {turn.model}</span>
      <span title={turn.requestId}>{pick("请求", "Request")} {turn.requestId.slice(0, 8)}</span>
    </div>}
  </section>;
}
