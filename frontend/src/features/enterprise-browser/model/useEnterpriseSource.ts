import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuthUser } from "@/features/auth/model/AuthContext";
import { requestEnterpriseSources } from "@/entities/modeling/api/modelingApi";
import type { components } from "@/shared/api/generated/schema";
type EnterpriseSourceDTO = components["schemas"]["EnterpriseSourceDTO"];
import { handleApiError } from "@/shared/api/http";

function savedSelection(key: string): { mode?: string; dataset?: string } {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(key) ?? "{}");
    if (!parsed || typeof parsed !== "object") return {};
    const value = parsed as Record<string, unknown>;
    return { mode: value.mode === "sample" || value.mode === "uploaded" ? value.mode : undefined, dataset: typeof value.dataset === "string" ? value.dataset : undefined };
  } catch { return {}; }
}

export function useEnterpriseSource() {
  const user = useAuthUser();
  const storageKey = `risk:enterprise-source:${user?.userId ?? ""}`;
  const [params, setParams] = useSearchParams();
  const [sources, setSources] = useState<EnterpriseSourceDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const saved = savedSelection(storageKey);
  const mode = params.get("source") ?? saved.mode ?? (sources.length ? "uploaded" : "sample");
  const datasetId = mode === "uploaded" ? params.get("dataset") ?? saved.dataset ?? sources[0]?.id ?? "" : "";
  const selected = sources.find((source) => source.id === datasetId);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const batches = await Promise.all(Array.from({ length: pages }, (_, index) => requestEnterpriseSources({ pagination: { page: index + 1, pageSize: 100 } })));
        if (!active) return;
        const items = batches.flatMap((batch) => batch.items);
        setSources(items); setTotal(batches[0].total); setError("");
        if (items.some((item) => item.importStatus === "pending" || item.importStatus === "failed")) {
          timer = setTimeout(() => void load(), 5000);
        }
      } catch (cause) {
        if (active) setError(handleApiError(cause));
      } finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [revision, pages]);

  useEffect(() => {
    if (!loading && !error) {
      try { localStorage.setItem(storageKey, JSON.stringify({ mode, dataset: datasetId })); } catch { /* Storage may be disabled in private browsing. */ }
    }
  }, [mode, datasetId, loading, error, storageKey]);

  function select(value: string) {
    const nextMode = value === "sample" ? "sample" : "uploaded";
    try { localStorage.setItem(storageKey, JSON.stringify({ mode: nextMode, dataset: value === "sample" ? "" : value })); } catch { /* Keep URL selection usable without storage. */ }
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      next.set("source", nextMode);
      if (value === "sample") next.delete("dataset"); else next.set("dataset", value);
      next.delete("model");
      return next;
    });
  }
  return { sources, loading, error, mode, datasetId, selected, select, total,
    loadMore: () => setPages((value) => value + 1), retry: () => setRevision((value) => value + 1) };
}
