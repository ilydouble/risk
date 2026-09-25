import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import * as BenchmarkApi from "@/entities/benchmark/api/benchmarkApi";
import { useBenchmark } from "@/features/benchmark/model/useBenchmark";
import BenchmarkShell from "@/features/benchmark/ui/BenchmarkShell";
import BenchmarkState from "@/features/benchmark/ui/BenchmarkState";
import Card from "@/shared/ui/Card";

export default function BenchmarkGraph() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const { data, loading, error, retry } = useBenchmark(`graph:${id}`, () => BenchmarkApi.requestGraphBenchmark({ id, limit: 100 }));
  const positions = useMemo(() => {
    const others = data?.nodes.filter((node) => node.id !== id) ?? [];
    const result = new Map<string, { x: number; y: number }>([[id, { x: 420, y: 240 }]]);
    others.forEach((node, index) => {
      const angle = 2 * Math.PI * index / Math.max(1, others.length) - Math.PI / 2;
      result.set(node.id, { x: 420 + 275 * Math.cos(angle), y: 240 + 180 * Math.sin(angle) });
    });
    return result;
  }, [data, id]);
  return <BenchmarkShell title={`${t("benchmark.graph")} · ${id}`}>
    <BenchmarkState loading={loading} error={error} retry={retry} />
    {data && !error && <>
      <Card title={t("benchmark.graph")} subtitle={t("benchmark.graphNote")} bodyClassName="p-3">
        <div className="overflow-x-auto"><svg viewBox="0 0 840 480" className="min-w-[640px] w-full" role="img" aria-label={t("benchmark.graph")}>
          <defs><marker id="benchmark-arrow" markerWidth="8" markerHeight="8" refX="10" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="none" stroke="currentColor" className="text-foreground-500" /></marker></defs>
          {data.edges.map((edge, index) => { const a = positions.get(edge.source); const b = positions.get(edge.target); if (!a || !b) return null; const length = Math.hypot(b.x - a.x, b.y - a.y) || 1; const inset = edge.target === id ? 30 : 22; return <line key={`${edge.source}-${edge.target}-${edge.relation}-${index}`} x1={a.x} y1={a.y} x2={b.x - (b.x - a.x) * inset / length} y2={b.y - (b.y - a.y) * inset / length} stroke="currentColor" className="text-foreground-500/60" strokeWidth="1.5" markerEnd="url(#benchmark-arrow)" />; })}
          {data.nodes.map((node) => { const p = positions.get(node.id); if (!p) return null; return <g key={node.id}><circle cx={p.x} cy={p.y} r={node.id === id ? 26 : 18} className={node.id === id ? "fill-primary-500" : node.kind === "person" ? "fill-accent-500" : "fill-background-300"} /><text x={p.x} y={p.y + 4} textAnchor="middle" className="fill-foreground-950 text-[10px]">{node.id}</text></g>; })}
        </svg></div>
      </Card>
      <Card title={t("benchmark.relationships", { count: data.totalEdges })} bodyClassName="divide-y divide-background-200">
        {data.edges.map((edge, index) => <div key={`${edge.source}-${edge.target}-${edge.relation}-${index}`} className="flex flex-wrap gap-3 px-4 py-2.5 text-xs"><span className="font-mono text-primary-400">{edge.source}</span><span className="text-foreground-500">→ {edge.relation} →</span><span className="font-mono text-primary-400">{edge.target}</span><span className="ml-auto font-mono text-foreground-500">{edge.weight.toFixed(3)}</span></div>)}
      </Card>
      {data.truncated && <p className="text-xs text-accent-400">{t("benchmark.truncated")}</p>}
      <Link to={`/benchmark/company/${id}`} className="inline-block rounded-md border border-background-300 px-4 py-2 text-sm text-foreground-800">{t("benchmark.profile")}</Link>
    </>}
  </BenchmarkShell>;
}
