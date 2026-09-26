import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { handleApiError } from "@/shared/api/http";

export function useBenchmark<T>(key: string, load: () => Promise<T>) {
  const { t } = useTranslation();
  const latest = useRef({ load, t });
  latest.current = { load, t };
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setData(null);
    setError("");
    latest.current.load().then((result) => {
      if (active) { setData(result); setError(""); }
    }).catch((failure) => {
      if (active) setError(handleApiError(failure, {
        BENCHMARK_MODEL_UNAVAILABLE: latest.current.t("benchmark.errorUnavailable"),
        BENCHMARK_COMPANY_NOT_FOUND: latest.current.t("benchmark.errorMissing"),
      }));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
    // Benchmark responses have no locale. A translation change must not discard the graph and its viewport.
  }, [key, revision]);

  const retry = () => { setLoading(true); setError(""); setRevision((value) => value + 1); };
  return { data, loading, error, retry };
}
