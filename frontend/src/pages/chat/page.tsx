import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowDown, ArrowUp, Bot, MessageSquare, Plus, RefreshCw, Settings2, Square } from "lucide-react";
import { motion } from "motion/react";
import { useAiModelConfig } from "@/features/ai-model-config/model/context";
import { useConversation } from "@/features/assistant/model/useConversation";
import SelectMenu from "@/shared/ui/SelectMenu";
import { useLang } from "@/shared/lib/useLang";
import { TurnTimeline } from "./ui/TurnTimeline";
import "./chat-markdown.css";

export default function ChatPage() {
  const config = useAiModelConfig();
  const { pick, lang } = useLang();
  const [params, setParams] = useSearchParams();
  const id = params.get("conversation");
  const select = useCallback((value: string) => setParams({ conversation: value }), [setParams]);
  const chat = useConversation(id, select);
  const [input, setInput] = useState("");
  const scroll = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const [showBottom, setShowBottom] = useState(false);
  const model = config.custom ? config.model : config.defaults?.model;
  const ready = !config.custom || Boolean(config.url.trim() && config.model.trim());
  const blocked = chat.sending || chat.loading || Boolean(chat.active);

  useEffect(() => {
    if (follow.current) scroll.current?.scrollTo({ top: scroll.current.scrollHeight });
  }, [chat.turns]);
  useEffect(() => { follow.current = true; }, [id]);

  async function send() {
    if (!input.trim() || blocked || !ready) return;
    if (await chat.send(input, { connection: config.connection, maxTokens: config.maxTokens, lang })) setInput("");
  }
  const errorText = chat.error === "STREAM_DISCONNECTED" ? pick("连接已中断，执行记录已保留。点击重新连接。", "Connection lost. Your work is saved. Reconnect to continue.")
    : chat.error === "ASSISTANT_BUSY" ? pick("这个对话已有任务执行中，请重新加载。", "This conversation is already running. Reload it.")
    : chat.error === "ASSISTANT_CAPACITY" ? pick("Agent 当前繁忙，请稍后重试。", "The assistant is busy. Please retry shortly.") : chat.error;

  return <div className="flex h-[calc(100dvh-9rem)] min-h-[560px] overflow-hidden rounded-2xl border border-background-200 bg-background-100 shadow-sm">
    <aside className="hidden w-56 shrink-0 flex-col border-r border-background-200 bg-background-50/70 p-3 md:flex">
      <button disabled={chat.sending} onClick={() => { setParams({}); setInput(""); }} className="mb-5 flex items-center gap-2 rounded-xl border border-background-200 px-3 py-2.5 text-sm hover:bg-background-200 disabled:opacity-50"><Plus size={16} />{pick("新对话", "New conversation")}</button>
      <p className="mb-2 px-2 text-xs font-medium text-foreground-400">{pick("最近对话", "Recent conversations")}</p>
      <nav aria-label={pick("历史对话", "Conversation history")} className="flex-1 space-y-1 overflow-y-auto">
        {chat.conversations.map(conversation => <button key={conversation.id} disabled={chat.sending} onClick={() => select(conversation.id)} className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2.5 text-left text-sm ${id === conversation.id ? "bg-background-200 text-foreground-900" : "text-foreground-500 hover:bg-background-200/60"}`}>
          <MessageSquare size={14} className="shrink-0" /><span className="truncate">{conversation.title || pick("新对话", "New conversation")}</span>
        </button>)}
      </nav>
      <p className="mt-4 border-t border-background-200 px-2 pt-3 text-xs leading-5 text-foreground-400">{pick("对话与执行过程自动保存", "Conversations and activity are saved automatically")}</p>
    </aside>
    <main className="relative flex min-w-0 flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-background-200 px-5 py-4">
        <div><h1 className="flex items-center gap-2 text-base font-semibold"><Bot size={18} className="text-primary-500" />{pick("智能助手", "Assistant")}</h1>
          <p className="mt-1 text-xs text-foreground-400">{model || pick("后端默认模型", "Default model")} · Strands</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setParams({})} disabled={chat.sending} className="md:hidden" title={pick("新对话", "New conversation")}><Plus size={18} /></button>
          <Link to="/settings/ai-model" className="rounded-lg p-2 text-foreground-500 hover:bg-background-200" title={pick("模型设置", "Model settings")}><Settings2 size={18} /></Link>
        </div>
      </header>
      {chat.conversations.length > 0 && !chat.sending && <div className="border-b border-background-200 px-5 py-2 md:hidden">
        <SelectMenu label={pick("历史对话", "History")} value={id || "new"}
          options={[{ value: "new", label: pick("新对话", "New conversation") }, ...chat.conversations.map(c => ({ value: c.id, label: c.title || pick("新对话", "New conversation") }))]}
          onChange={value => value === "new" ? setParams({}) : select(value)} />
      </div>}
      <div ref={scroll} onScroll={() => { const el = scroll.current; if (el) { follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; setShowBottom(!follow.current); } }} className="flex-1 overflow-y-auto overscroll-contain px-5 py-8 sm:px-8">
        <div className="mx-auto max-w-3xl space-y-9">
          {!chat.loading && chat.turns.length === 0 && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-lg py-16 text-center">
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-500/10 text-primary-500"><Bot size={28} /></div>
            <h2 className="text-2xl font-semibold tracking-tight">{pick("从一个问题开始", "Start with a question")}</h2>
            <p className="mt-3 text-sm leading-7 text-foreground-500">{pick("在这里查看回答、推理和工具执行过程。可查询时间、检索演示企业并查看关系图谱。", "Follow answers, reasoning, and tool activity here. Check the time, search demo companies and view their relationship graphs.")}</p>
            <button onClick={() => setInput(pick("请用工具查一下上海现在的时间，再告诉我结果。", "Use the tool to check the current time in Shanghai."))} className="mt-7 rounded-xl border border-background-200 px-4 py-3 text-sm text-foreground-600 hover:border-primary-400">{pick("查询当前时间，体验工具调用", "Try a live time lookup")}</button>
          </motion.div>}
          {chat.loading && <p role="status" className="py-10 text-center text-sm text-foreground-400">{pick("正在恢复会话…", "Restoring conversation…")}</p>}
          {chat.turns.map(turn => <TurnTimeline key={turn.id} turn={turn} />)}
        </div>
      </div>
      {showBottom && <button onClick={() => { follow.current = true; scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: "smooth" }); }} className="absolute bottom-44 right-8 rounded-full border border-background-200 bg-background-100 p-2 shadow-md" title={pick("回到最新消息", "Jump to latest")}><ArrowDown size={16} /></button>}
      <div className="px-5 pb-4 pt-2 sm:px-8">
        <div className="mx-auto max-w-3xl">
          {errorText && <div role="alert" className="mb-3 flex items-center gap-3 rounded-xl bg-red-500/10 p-3 text-xs text-red-500"><span className="flex-1">{errorText}</span><button onClick={chat.retry} className="flex items-center gap-1"><RefreshCw size={13} />{pick("重新连接", "Reconnect")}</button></div>}
          {chat.active && chat.connection === "reconnecting" && <p role="status" className="mb-2 text-xs text-foreground-500">{pick("正在恢复连接，Agent 继续执行…", "Reconnecting. The Agent is still working…")}</p>}
          <form onSubmit={event => { event.preventDefault(); void send(); }} className="rounded-2xl border border-background-300 bg-background-50 p-3 focus-within:border-primary-400">
            <textarea aria-label={pick("发送消息", "Message")} rows={2} maxLength={8000} value={input} onChange={event => setInput(event.target.value)} disabled={chat.sending} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); } }} placeholder={pick("输入问题，Enter 发送，Shift + Enter 换行", "Ask anything. Enter to send, Shift + Enter for a new line")} className="max-h-40 w-full resize-none bg-transparent px-1 py-1 text-sm leading-6 outline-none" />
            <div className="flex items-center justify-between pt-1">
              <span className="px-1 text-xs text-foreground-400">{chat.sending ? pick("正在提交…", "Submitting…") : pick("执行记录自动保存", "Activity is saved automatically")}</span>
              {chat.active ? <button type="button" onClick={() => void chat.cancel()} className="flex items-center gap-2 rounded-xl bg-foreground-900 px-3 py-2 text-xs text-background-50"><Square size={13} fill="currentColor" />{pick("停止", "Stop")}</button>
                : <button type="submit" disabled={blocked || !input.trim() || !ready} aria-label={pick("发送", "Send")} className="rounded-xl bg-primary-500 p-2.5 text-white disabled:opacity-30"><ArrowUp size={17} /></button>}
            </div>
          </form>
          <p className="mt-2 text-center text-[11px] text-foreground-400">{pick("推理内容取决于模型端点支持；请核验重要信息。", "Reasoning availability depends on the model endpoint. Verify important information.")}</p>
        </div>
      </div>
    </main>
  </div>;
}
