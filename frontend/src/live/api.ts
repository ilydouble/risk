import { useEffect, useState } from 'react';

export type Company = { id: string; name: string; community: string; split: string; event_count: number; risk_probability: number; predicted_label: number; credit_score: number };
export type Listing = { total: number; items: Company[]; dataset: string };
export type Detail = Company & { dataset: string; features: Record<string, number | null>; observed_label: number | null; events: { cause: number; court: number; result: number; age_months: number }[] };
export type Explanation = { company_id: string; risk_probability: number; features: { feature: string; value: number | null; probability_delta: number; probability_without_feature: number }[] };
export type Graph = { center: string; total_edges: number; truncated: boolean; nodes: { id: string; kind: string; community: string }[]; edges: { source: string; target: string; relation: string; weight: number }[] };
export type Metric = { n: number; positives: number; roc_auc: number; pr_auc: number; ks: number; brier: number; f1: number; precision: number; recall: number };
export type Evaluation = { model: string; mode: string; seed: number; dataset: string; threshold: number; best_epoch: number; metrics: Record<string, Metric>; company_count: number; relation_count: number; synthetic: boolean };

export async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, { signal });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { const body = await response.json(); if (typeof body.detail === 'string') detail = body.detail; } catch { /* preserve HTTP status */ }
    throw new Error(detail);
  }
  return response.json();
}
export function useApi<T>(path: string) {
  const [state, setState] = useState<{ path: string; data?: T; error?: string }>({ path: '' });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ path });
    request<T>(path, controller.signal).then(data => setState({ path, data })).catch(error => {
      if (!controller.signal.aborted) setState({ path, error: error.message });
    });
    return () => controller.abort();
  }, [path, attempt]);
  return { ...(state.path === path ? state : {}), retry: () => setAttempt(v => v + 1) };
}
export const featureNames: Record<string, string> = {
  log_registered_capital: '注册资本（log1p）', log_paid_capital: '实缴资本（log1p）', age_months: '企业年龄（月）',
};
export const percent = (v: number) => `${(v * 100).toFixed(2)}%`;
