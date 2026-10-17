import { useEffect, useState } from "react";
import * as GraphApi from "@/entities/graph/api/graphApi";
import type { ResponseGetGraph } from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { useLang } from "@/shared/lib/useLang";
import CompanyGraph from "./CompanyGraph";

const noRiskPath = new Set<string>();

export default function CompanyGraphPanel({ companyId, depth, height = 420 }: {
  companyId: string;
  depth: number;
  height?: number;
}) {
  const { pick, lang } = useLang();
  const [data, setData] = useState<ResponseGetGraph["graph"] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setData(null); setError(""); setSelected(null);
    void GraphApi.requestGetGraph({ companyId, depth, lang }).then(response => {
      if (active) setData(response.graph);
    }).catch(cause => {
      if (active) setError(handleApiError(cause));
    });
    return () => { active = false; };
  }, [companyId, depth, lang, attempt]);
  if (error) return <div role="alert" className="space-y-3 py-8 text-sm">
    <p>{error}</p><button onClick={() => setAttempt(value => value + 1)} className="rounded border px-3 py-2">{pick("重试", "Retry")}</button>
  </div>;
  if (!data) return <p role="status" className="py-8 text-sm">{pick("正在加载图谱…", "Loading graph…")}</p>;
  const node = data.nodes.find(value => value.id === selected);
  return <div className="space-y-3">
    <p className="text-xs text-foreground-500">{pick(`${data.nodes.length} 个节点 · ${data.edges.length} 条关系`, `${data.nodes.length} nodes · ${data.edges.length} relationships`)}</p>
    <CompanyGraph nodes={data.nodes} edges={data.edges} selectedId={selected} onSelect={setSelected}
      focusRisk={false} onRiskPath={noRiskPath} height={height} />
    {node && <div className="rounded-lg bg-background-100 p-3 text-sm">
      <p className="font-medium">{node.label}</p>
      <p className="mt-1 text-xs text-foreground-500">{node.relation} · {node.exposure}</p>
      {node.note && <p className="mt-2 text-xs leading-6">{node.note}</p>}
    </div>}
  </div>;
}
