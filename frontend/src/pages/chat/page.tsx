import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAiModelConfig } from "@/features/ai-model-config/model/context";
import { http, handleApiError } from "@/shared/api/http";
import type { components } from "@/shared/api/generated/schema";

type Message = components["schemas"]["ChatMessage"];
const complete = http.withTimeout(70000).post<
  components["schemas"]["RequestChat"], components["schemas"]["ResponseChat"]
>("/chat/complete");
const errors = {
  CHAT_NOT_CONFIGURED: "默认模型尚未配置密钥，请前往智能体模型设置。",
  CHAT_UNREACHABLE: "后端无法连接所选模型，请检查地址和网络。",
  CHAT_TIMEOUT: "大模型响应超时，请稍后重试并检查服务负载。",
  CHAT_AUTH_FAILED: "大模型认证失败，请检查所选模型的密钥。",
  CHAT_UPSTREAM_ERROR: "大模型服务返回错误，请检查所选模型的服务状态。",
  CHAT_INVALID_RESPONSE: "大模型返回格式异常或回答为空。",
  REQUEST_INVALID: "模型配置无效，请检查接口地址和模型名。",
};

export default function ChatPage() {
  const config = useAiModelConfig();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ model: string; elapsedMs: number } | null>(null);
  const busy = useRef(false);
  const modelReady = !config.custom || Boolean(config.url.trim() && config.model.trim());
  const selectedModel = config.custom ? config.model.trim() || "尚未填写模型名" : config.defaults?.model || "后端默认模型";

  async function send(question: string) {
    if (busy.current || !question.trim() || !modelReady) return;
    const next: Message[] = [...messages, { role: "user", content: question.trim() }];
    if (next.length > 20 || next.reduce((n, m) => n + m.content.length, 0) > 32000) {
      setError("对话已达到长度限制，请清空对话后继续。");
      return;
    }
    busy.current = true;
    setPending(true);
    setError("");
    setResult(null);
    try {
      const answer = await complete({ messages: next, connection: config.connection });
      setMessages([...next, { role: "assistant", content: answer.content }]);
      setResult({ model: answer.model, elapsedMs: answer.elapsedMs });
      setInput("");
    } catch (cause) {
      setError(handleApiError(cause, errors));
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-foreground-950">模型问答</h1>
        <p className="mt-2 text-sm text-foreground-500">使用智能体模型设置中的模型提问。对话仅保留在当前页面；暂未连接企业资料或风险预测结果。</p>
      </div>
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-background-200 bg-background-100 px-4 py-3 text-sm">
        <span className="text-foreground-500">当前模型：</span>
        <strong>{selectedModel}</strong>
        <span className="text-foreground-500">{config.custom ? "自定义模型" : "后端默认模型"}</span>
        <Link to="/settings/ai-model" className="ml-auto text-primary-400 underline">修改模型配置</Link>
      </div>
      {!modelReady && <p role="alert" className="text-sm text-red-500">请先在智能体模型设置中填写接口地址和模型名。</p>}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-background-200 bg-background-100 p-4">
        <button type="button" disabled={pending || !modelReady} onClick={() => void send("你好，请简短介绍一下自己，并回复：连接测试成功。")} className="rounded-md bg-primary-500 px-4 py-2 text-sm text-white disabled:opacity-50">一键测试连接</button>
        <button type="button" disabled={pending} onClick={() => { setMessages([]); setError(""); setResult(null); setInput(""); }} className="rounded-md border border-background-300 px-4 py-2 text-sm disabled:opacity-50">清空对话</button>
        <span role="status" className="text-sm text-foreground-500">{pending ? "正在等待大模型回答…" : error ? "调用失败" : result ? `调用成功 · ${result.model} · ${(result.elapsedMs / 1000).toFixed(2)} 秒` : "尚未测试"}</span>
      </div>
      {error && <div role="alert" className="rounded-lg border border-red-400/40 bg-red-500/10 p-4 text-sm text-red-500">{error}</div>}
      <div aria-live="polite" className="min-h-64 space-y-4 rounded-lg border border-background-200 bg-background-100 p-5">
        {messages.length === 0 && <p className="py-16 text-center text-sm text-foreground-500">点击“一键测试连接”，或输入问题开始对话。</p>}
        {messages.map((message, index) => <div key={index} className={`rounded-lg p-4 ${message.role === "user" ? "bg-primary-500/10" : "bg-background-50"}`}>
          <p className="mb-2 text-xs font-medium text-foreground-500">{message.role === "user" ? "你" : "大模型"}</p>
          <p className="whitespace-pre-wrap break-words text-sm leading-7">{message.content}</p>
        </div>)}
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void send(input); }} className="space-y-3">
        <label htmlFor="chat-question" className="text-sm font-medium">输入问题</label>
        <textarea id="chat-question" value={input} onChange={(event) => setInput(event.target.value)} maxLength={8000} disabled={pending} rows={4} placeholder="例如：经营风险分析通常需要哪些企业信息？" className="w-full rounded-lg border border-background-300 bg-background-100 p-3 text-sm outline-none focus:border-primary-500 disabled:opacity-50" />
        <div className="flex items-center justify-between">
          <span className="text-xs text-foreground-500">{input.length} / 8000 · 单次回答最多 1024 tokens</span>
          <button type="submit" disabled={pending || !modelReady || !input.trim()} className="rounded-md bg-primary-500 px-5 py-2 text-sm text-white disabled:opacity-50">{pending ? "发送中…" : "发送"}</button>
        </div>
      </form>
    </div>
  );
}
