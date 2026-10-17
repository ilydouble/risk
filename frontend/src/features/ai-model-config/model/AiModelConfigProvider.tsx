import { useEffect, useState, type ReactNode } from "react";
import { requestModelDefaults } from "@/features/ai-model-config/api/modelConfigApi";
import { AiModelContext } from "./context";
import type { ResponseModelDefaults } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";

const storageKey = "risk:data-prep:model:v1";
const maxTokensStorageKey = "risk:ai-model:max-tokens:v1";
const outputLimits = [1024, 2048, 4096, 8192, 16384];

export function AiModelConfigProvider({ children }: { children: ReactNode }) {
  const [defaults, setDefaults] = useState<ResponseModelDefaults>();
  const [loading, setLoading] = useState(true);
  const [custom, setCustom] = useState(false);
  const [url, setUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [maxTokens, setMaxTokensState] = useState(() => {
    const saved = Number(window.localStorage.getItem(maxTokensStorageKey));
    return outputLimits.includes(saved) ? saved : 4096;
  });

  useEffect(() => {
    let active = true;
    const saved = window.localStorage.getItem(storageKey);
    if (saved) {
      try {
        const value = JSON.parse(saved) as { url: string; model: string };
        if (value.url && value.model) {
          setCustom(true);
          setUrl(value.url);
          setModel(value.model);
        }
      } catch { window.localStorage.removeItem(storageKey); }
    }
    requestModelDefaults({}).then((value) => {
      if (active) setDefaults(value);
    }).catch((cause) => {
      if (active) handleApiError(cause);
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const connection = custom
    ? { url: url.trim(), model: model.trim(), apiKey }
    : undefined;

  return <AiModelContext.Provider value={{
    defaults, loading, custom, url, model, apiKey, maxTokens, connection,
    setCustom, setUrl, setModel, setApiKey,
    setMaxTokens(value) {
      if (!outputLimits.includes(value)) return;
      setMaxTokensState(value);
      window.localStorage.setItem(maxTokensStorageKey, String(value));
    },
    useOpenLux() {
      setCustom(true);
      setUrl("https://api.openlux.ai/v1/chat/completions");
      setModel("qwen3.6-35b-a3b");
      setApiKey("");
    },
    save() {
      window.localStorage.setItem(storageKey, JSON.stringify({ url: url.trim(), model: model.trim() }));
    },
  }}>{children}</AiModelContext.Provider>;
}
