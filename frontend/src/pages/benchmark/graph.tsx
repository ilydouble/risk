import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import * as BenchmarkApi from "@/entities/benchmark/api/benchmarkApi";
import { useBenchmark } from "@/features/benchmark/model/useBenchmark";
import BenchmarkShell from "@/features/benchmark/ui/BenchmarkShell";
import BenchmarkState from "@/features/benchmark/ui/BenchmarkState";
import Card from "@/shared/ui/Card";
import { GraphView } from "@/shared/ui/graph";
import { chartPalette } from "@/shared/config/theme/palette";

export default function BenchmarkGraph() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const { data, loading, error, retry } = useBenchmark(`graph:${id}`, () => BenchmarkApi.requestGraphBenchmark({ id, limit: 100 }));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const graph = useMemo(() => {
    const occurrences = new Map<string, number>();
    return {
      nodes: (data?.nodes ?? []).map((node) => ({
        id: node.id,
        label: node.id,
        color: node.kind === "person" ? chartPalette.accent : chartPalette.primary,
      })),
      edges: (data?.edges ?? []).map((edge) => {
        // The API has no edge ID. Include direction and duplicate occurrence to retain every record.
        const key = JSON.stringify([edge.source, edge.target, edge.relation, edge.weight]);
        const occurrence = occurrences.get(key) ?? 0;
        occurrences.set(key, occurrence + 1);
        return {
          id: `benchmark:${key}:${occurrence}`,
          source: edge.source,
          target: edge.target,
          label: `${edge.relation} · ${edge.weight.toFixed(3)}`,
        };
      }),
    };
  }, [data]);
  return <BenchmarkShell title={`${t("benchmark.graph")} · ${id}`}>
    <BenchmarkState loading={loading} error={error} retry={retry} />
    {data && !error && <>
      <Card title={t("benchmark.graph")} subtitle={t("benchmark.graphNote")} bodyClassName="p-3">
        <GraphView {...graph} centerId={data.center} selectedId={selectedId} onSelect={setSelectedId} height={520} ariaLabel={t("benchmark.graph")} />
      </Card>
      <Card title={t("benchmark.relationships", { count: data.totalEdges })} bodyClassName="divide-y divide-background-200">
        {data.edges.map((edge, index) => <div key={`${edge.source}-${edge.target}-${edge.relation}-${index}`} className="flex flex-wrap gap-3 px-4 py-2.5 text-xs"><span className="font-mono text-primary-400">{edge.source}</span><span className="text-foreground-500">→ {edge.relation} →</span><span className="font-mono text-primary-400">{edge.target}</span><span className="ml-auto font-mono text-foreground-500">{edge.weight.toFixed(3)}</span></div>)}
      </Card>
      {data.truncated && <p className="text-xs text-accent-400">{t("benchmark.truncated")}</p>}
      <Link to={`/benchmark/company/${id}`} className="inline-block rounded-md border border-background-300 px-4 py-2 text-sm text-foreground-800">{t("benchmark.profile")}</Link>
    </>}
  </BenchmarkShell>;
}
