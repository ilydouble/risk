import { useState } from "react";
import type { ResponseEnterpriseCompany } from "@/shared/api/generated/schema";
import DatasetGraphPanel from "@/features/company-graph/ui/DatasetGraphPanel";
import Card from "@/shared/ui/Card";
import { useLang } from "@/shared/lib/useLang";

export function EnterpriseRelationGraph({ data }: { data: ResponseEnterpriseCompany }) {
  const [depth, setDepth] = useState(1);
  const { pick } = useLang();
  return <div id="enterprise-graph" className="scroll-mt-6"><Card title={pick("企业关系图谱", "Enterprise graph")} icon="ri-share-line" bodyClassName="space-y-4 p-5">
    <label className="text-sm">{pick("关系跳数", "Depth")} <select aria-label={pick("关系跳数", "Graph depth")} className="rounded border border-background-300 bg-background-50 p-1" value={depth} onChange={e => setDepth(Number(e.target.value))}>{[1, 2, 3].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
    <DatasetGraphPanel datasetId={data.dataset.id} companyId={data.company.nodeId!} depth={depth} height={480} />
  </Card></div>;
}
