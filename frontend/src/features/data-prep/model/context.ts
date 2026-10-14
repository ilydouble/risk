import { createContext, useContext, type Dispatch, type SetStateAction } from "react";
import type { ResponseInspectData, ResponseSuggestMapping } from "@/shared/api/generated/schema";

export type DataPrepSession = {
  file?: File;
  profile?: ResponseInspectData;
  suggestion?: ResponseSuggestMapping;
  setFile: Dispatch<SetStateAction<File | undefined>>;
  setProfile: Dispatch<SetStateAction<ResponseInspectData | undefined>>;
  setSuggestion: Dispatch<SetStateAction<ResponseSuggestMapping | undefined>>;
};

export const DataPrepContext = createContext<DataPrepSession | null>(null);

export function useDataPrepSession(): DataPrepSession {
  const value = useContext(DataPrepContext);
  if (!value) throw new Error("Data preparation session provider is missing");
  return value;
}
