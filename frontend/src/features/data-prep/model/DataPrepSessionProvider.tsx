import { useState, type ReactNode } from "react";
import { DataPrepContext } from "./context";
import type { ResponseInspectData, ResponseSuggestMapping } from "@/shared/api/generated/schema";

export function DataPrepSessionProvider({ children }: { children: ReactNode }) {
  const [file, setFile] = useState<File>();
  const [profile, setProfile] = useState<ResponseInspectData>();
  const [suggestion, setSuggestion] = useState<ResponseSuggestMapping>();
  return <DataPrepContext.Provider value={{ file, profile, suggestion, setFile, setProfile, setSuggestion }}>
    {children}
  </DataPrepContext.Provider>;
}
