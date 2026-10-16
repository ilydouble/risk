import { useEffect, useState } from "react";
import type { ResponsePreparation } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { requestGetPreparation } from "../api/dataPrepApi";

export function useAssistantPreparation(id: string | null) {
  const [result, setResult] = useState<{ id: string; preparation?: ResponsePreparation; error?: string }>();
  useEffect(() => {
    if (!id) return;
    let active = true;
    requestGetPreparation({ preparationId: id }).then(preparation => {
      if (active) setResult({ id, preparation });
    }).catch(cause => {
      if (active) setResult({ id, error: handleApiError(cause) });
    });
    return () => { active = false; };
  }, [id]);
  const current = result?.id === id ? result : undefined;
  return {
    preparation: current?.preparation,
    error: current?.error,
    loading: Boolean(id && !current),
    onSaved: (preparation: ResponsePreparation) => setResult({ id: preparation.id, preparation }),
  };
}
