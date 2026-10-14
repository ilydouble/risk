import { createContext, useContext } from "react";
import type { RequestTestModel, ResponseModelDefaults } from "@/shared/api/generated/schema";

export type AiModelConfig = {
  defaults?: ResponseModelDefaults;
  loading: boolean;
  custom: boolean;
  url: string;
  model: string;
  apiKey: string;
  maxTokens: number;
  connection?: RequestTestModel["connection"];
  setCustom(value: boolean): void;
  setUrl(value: string): void;
  setModel(value: string): void;
  setApiKey(value: string): void;
  setMaxTokens(value: number): void;
  useOpenLux(): void;
  save(): void;
};

export const AiModelContext = createContext<AiModelConfig | null>(null);

export function useAiModelConfig(): AiModelConfig {
  const value = useContext(AiModelContext);
  if (!value) throw new Error("AI model configuration provider is missing");
  return value;
}
