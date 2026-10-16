import { useState, type ReactNode } from "react";
import { DataPrepContext } from "./context";
import type { ResponseInspectData, ResponseSuggestMapping, ResponsePreparation } from "@/shared/api/generated/schema";

export function DataPrepSessionProvider({ children }: { children: ReactNode }) {
  const [files, setFiles] = useState<File[]>([]);
  const [profile, setProfile] = useState<ResponseInspectData>();
  const [suggestion, setSuggestion] = useState<ResponseSuggestMapping>();
  const [preparation, setPreparation] = useState<ResponsePreparation>();
  return <DataPrepContext.Provider value={{ files, profile, suggestion, preparation, setPreparation, setFiles, setProfile, setSuggestion }}>
    {children}
  </DataPrepContext.Provider>;
}
