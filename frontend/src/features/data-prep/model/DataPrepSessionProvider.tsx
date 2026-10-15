import { useState, type ReactNode } from "react";
import { DataPrepContext } from "./context";
import type { ResponseInspectData, ResponseSuggestMapping, ResponsePreparation } from "@/shared/api/generated/schema";

export function DataPrepSessionProvider({ children }: { children: ReactNode }) {
  const [file, setFile] = useState<File>();
  const [profile, setProfile] = useState<ResponseInspectData>();
  const [suggestion, setSuggestion] = useState<ResponseSuggestMapping>();
  const [preparation, setPreparation] = useState<ResponsePreparation>();
  return <DataPrepContext.Provider value={{ file, profile, suggestion, preparation, setPreparation, setFile, setProfile, setSuggestion }}>
    {children}
  </DataPrepContext.Provider>;
}
