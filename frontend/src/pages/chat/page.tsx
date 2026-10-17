import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowDown, ArrowUp, Bot, MessageSquare, Plus, RefreshCw, Settings2, Square } from "lucide-react";
import { motion } from "motion/react";
import { useAiModelConfig } from "@/features/ai-model-config/model/context";
import { useDataPrepSession } from "@/features/data-prep/model/context";
import { useAssistantPreparation } from "@/features/data-prep/model/useAssistantPreparation";
import { AssistantPreparationCard } from "@/features/data-prep/ui/AssistantPreparationCard";
import { useConversation } from "@/features/assistant/model/useConversation";
import SelectMenu from "@/shared/ui/SelectMenu";
import { useLang } from "@/shared/lib/useLang";
import { TurnTimeline } from "./ui/TurnTimeline";
import "./chat-markdown.css";

export default function ChatPage() {
  const config = useAiModelConfig();
  const dataPrep = useDataPrepSession();
  const { pick, lang } = useLang();
  const [params, setParams] = useSearchParams();
  const id = params.get("conversation");
  const preparationId = params.get("preparation");
  // Creating a conversation must retain its explicit case binding across navigation.
  const select = useCallback((value: string) => setParams(current => {
    const next = new URLSearchParams(current); next.set("conversation", value); return next;
  }), [setParams]);
  const chat = useConversation(id, select);
  const [input, setInput] = useState(() => {
    const dataset = params.get("riskDataset"), model = params.get("riskModel"), company = params.get("riskCompany");
    return dataset && model && company
      ? `请使用已发布模型 ${model}，预测数据集 ${dataset} 中企业 ${company} 的登记状态，并解释主要特征敏感性。请核对模型测试质量，保留警告，区分关系证据与风险贡献，并给出企业详情链接。`
      : "";
  });
  const openHistory = (value: string) => { setParams({ conversation: value }); setInput(""); };
  const mappingPrompt = "请读取当前案例的体检结果、已有报告和映射草稿，先总结主要问题，再从最影响导入的一个问题开始与我确认字段含义和处理规则。不要一次询问所有问题。";
  const scroll = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const [showBottom, setShowBottom] = useState(false);
  const model = config.custom ? config.model : config.defaults?.model;
  const ready = !config.custom || Boolean(config.url.trim() && config.model.trim());
  const blocked = chat.sending || chat.loading || Boolean(chat.active);
  const preparation = useAssistantPreparation(preparationId, `${blocked}:${chat.turns.length}`);

  useEffect(() => {
    if (follow.current) scroll.current?.scrollTo({ top: scroll.current.scrollHeight });
  }, [chat.turns]);
  useEffect(() => { follow.current = true; }, [id]);

  async function send(text = input) {
    if (text.length > (preparationId ? 7500 : 8000) || !text.trim() || blocked || !ready || (preparationId && !preparation.preparation)) return;
    const message = preparationId
      ? `${text.trim()}\n\n【当前案例上下文】只处理 preparation:${preparationId}；先读取该案例的最新统计、映射和报告。不确定的规则先询问；规则明确后可用 preparation_save_plan 保存可执行草稿、preparation_trial 试运行、preparation_result 查询结果。试运行不等于导入，正式导入须由用户在结果卡片确认。`
      : text;
    if (await chat.send(message, {
      connection: config.connection, maxTokens: config.maxTokens, lang,
      dataPrep: !preparationId && !dataPrep.preparation && dataPrep.profile && dataPrep.files[0] ? {
        filename: dataPrep.files[0].name, profile: dataPrep.profile, report: dataPrep.suggestion,
      } : undefined,
    })) setInput("");
  }
  const errorText = chat.error === "STREAM_DISCONNECTED" ? pick("连接已中断，执行记录已保留。点击重新连接。", "Connection lost. Your work is saved. Reconnect to continue.")
    : chat.error === "ASSISTANT_BUSY" ? pick("这个对话已有任务执行中，请重新加载。", "This conversation is already running. Reload it.")
    : chat.error === "ASSISTANT_CAPACITY" ? pick("Agent 当前繁忙，请稍后重试。", "The assistant is busy. Please retry shortly.") : chat.error;

  return <div className="flex h-[calc(100dvh-9rem)] min-h-[560px] overflow-hidden rounded-2xl border border-background-200 bg-background-100 shadow-sm">
    <aside className="hidden w-56 shrink-0 flex-col border-r border-background-200 bg-background-50/70 p-3 md:flex">
      <button disabled={chat.sending} onClick={() => { setParams({}); setInput(""); }} className="mb-5 flex items-center gap-2 rounded-xl border border-background-200 px-3 py-2.5 text-sm hover:bg-background-200 disabled:opacity-50"><Plus size={16} />{pick("新对话", "New conversation")}</button>
      <p className="mb-2 px-2 text-xs font-medium text-foreground-400">{pick("最近对话", "Recent conversations")}</p>
      <nav aria-label={pick("历史对话", "Conversation history")} className="flex-1 space-y-1 overflow-y-auto">
        {chat.conversations.map(conversation => <button key={conversation.id} disabled={chat.sending} onClick={() => openHistory(conversation.id)} className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2.5 text-left text-sm ${id === conversation.id ? "bg-background-200 text-foreground-900" : "text-foreground-500 hover:bg-background-200/60"}`}>
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
          <button onClick={() => { setParams({}); setInput(""); }} disabled={chat.sending} className="md:hidden" title={pick("新对话", "New conversation")}><Plus size={18} /></button>
          <Link to="/settings/ai-model" className="rounded-lg p-2 text-foreground-500 hover:bg-background-200" title={pick("模型设置", "Model settings")}><Settings2 size={18} /></Link>
        </div>
      </header>
      {preparation.loading && <p role="status" className="border-b border-background-200 px-5 py-3 text-sm">正在恢复当前案例…</p>}
      {preparation.error && <div role="alert" className="border-b border-background-200 px-5 py-3 text-sm text-red-500">案例无法读取：{preparation.error}。请返回数据准备重新选择。<Link className="ml-2 underline" to="/data-prep">返回数据准备</Link></div>}
      {preparation.preparation && <AssistantPreparationCard preparation={preparation.preparation} conversationId={id} disabled={blocked} onStart={() => void send(mappingPrompt)} onConvert={() => void send("请读取当前案例和已确认的方案，将明确的字段映射、去重及缺失处理保存为可执行规则并试运行。如果仍有未确定的业务规则，先逐项询问，不要猜测。返回实际核验结果，提示我在卡片中查看并确认导入。")} onSaved={preparation.onSaved} />}
      {chat.conversations.length > 0 && !chat.sending && <div className="border-b border-background-200 px-5 py-2 md:hidden">
        <SelectMenu label={pick("历史对话", "History")} value={id || "new"}
          options={[{ value: "new", label: pick("新对话", "New conversation") }, ...chat.conversations.map(c => ({ value: c.id, label: c.title || pick("新对话", "New conversation") }))]}
          onChange={value => { setInput(""); if (value === "new") setParams({}); else openHistory(value); }} />
      </div>}
      <div ref={scroll} onScroll={() => { const el = scroll.current; if (el) { follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; setShowBottom(!follow.current); } }} className="flex-1 overflow-y-auto overscroll-contain px-5 py-8 sm:px-8">
        <div className="mx-auto max-w-3xl space-y-9">
          {!preparationId && !chat.loading && chat.turns.length === 0 && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-lg py-16 text-center">
            <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-500/10 text-primary-500"><Bot size={28} /></div>
            <h2 className="text-2xl font-semibold tracking-tight">{pick("从一个问题开始", "Start with a question")}</h2>
            <p className="mt-3 text-sm leading-7 text-foreground-500">{pick("先发现企业演示数据、当前账号训练数据集，以及本页面会话的案例与报告，再按来源查询。", "Discover enterprise demo data, your training datasets, and cases and reports from this browser session before querying each source.")}</p>
            <button onClick={() => setInput(pick("请列出我能查看的数据资产，包括演示数据、上传案例和分析报告，说明来源与记录数。", "List available data assets, including demo data, uploaded cases and analysis reports, with their sources and record counts."))} className="mt-7 rounded-xl border border-background-200 px-4 py-3 text-sm text-foreground-600 hover:border-primary-400">{pick("查看统一数据资产目录", "Explore data assets")}</button>
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
            <textarea aria-label={pick("发送消息", "Message")} rows={2} maxLength={preparationId ? 7500 : 8000} value={input} onChange={event => setInput(event.target.value)} disabled={chat.sending} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); } }} placeholder={pick("输入问题，Enter 发送，Shift + Enter 换行", "Ask anything. Enter to send, Shift + Enter for a new line")} className="max-h-40 w-full resize-none bg-transparent px-1 py-1 text-sm leading-6 outline-none" />
            <div className="flex items-center justify-between pt-1">
              <span className="px-1 text-xs text-foreground-400">{chat.sending ? pick("正在提交…", "Submitting…") : pick("执行记录自动保存", "Activity is saved automatically")}</span>
              {chat.active ? <button type="button" onClick={() => void chat.cancel()} className="flex items-center gap-2 rounded-xl bg-foreground-900 px-3 py-2 text-xs text-background-50"><Square size={13} fill="currentColor" />{pick("停止", "Stop")}</button>
                : <button type="submit" disabled={blocked || !input.trim() || input.length > (preparationId ? 7500 : 8000) || !ready || Boolean(preparationId && !preparation.preparation)} aria-label={pick("发送", "Send")} className="rounded-xl bg-primary-500 p-2.5 text-white disabled:opacity-30"><ArrowUp size={17} /></button>}
            </div>
          </form>
          <p className="mt-2 text-center text-[11px] text-foreground-400">{preparationId ? "本轮围绕顶部案例展开；试运行通过后在核验卡片确认导入。" : dataPrep.preparation ? pick("已保存案例与报告可通过资产目录查询；刷新后仍可用。", "Saved cases and reports are available through the asset catalog after refresh.") : dataPrep.profile ? pick("本轮将携带当前案例统计和已有报告供模型查询；刷新后失效。", "This turn includes the current case profile and report for model queries; they expire on refresh.") : pick("目录覆盖共享演示数据与当前账号训练数据；本轮未携带页面案例。", "The catalog covers shared demo data and your training datasets; no browser case is attached.")}</p>
        </div>
      </div>
    </main>
  </div>;
}
