import { Network } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { ResponseCreateTurn } from "@/shared/api/generated/schema";
import { useLang } from "@/shared/lib/useLang";

type GraphReference = NonNullable<Extract<ResponseCreateTurn["turn"]["items"][number], { kind: "tool_call" }>["graph"]>;
const DatasetGraphPanel = lazy(() => import("./DatasetGraphPanel"));

export function GraphResultCard({ reference }: { reference: GraphReference }) {
  const { pick } = useLang();
  const viewport = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [placeholderHeight, setPlaceholderHeight] = useState(340);

  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    // Turn/process folds keep their children mounted. Only visible previews own a canvas.
    const observer = new IntersectionObserver(([entry]) => {
      // Keep the scroll position stable when a selected-node detail leaves the viewport.
      if (!entry.isIntersecting && entry.boundingClientRect.height > 0) {
        setPlaceholderHeight(entry.boundingClientRect.height);
      }
      setVisible(entry.isIntersecting);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return <section aria-label={reference.title} className="min-w-0 space-y-3 text-sm">
    <div className="flex items-start gap-2">
      <Network size={18} className="mt-0.5 shrink-0 text-primary-500" />
      <div className="min-w-0 flex-1">
        <p className="break-words font-medium">{reference.title}</p>
        <p className="mt-1 text-xs text-foreground-500">{reference.companyId} · {pick(`${reference.depth} 跳`, `${reference.depth} hops`)}</p>
      </div>
      <span className="shrink-0 rounded bg-amber-500/10 px-2 py-1 text-xs text-amber-600">{reference.demo ? pick("样例数据", "Sample data") : pick("数据集来源关系", "Dataset source graph")}</span>
    </div>
    <div ref={viewport} style={{ minHeight: visible ? 340 : placeholderHeight }}>
      {visible ? <Suspense fallback={<p role="status" className="py-8 text-sm text-foreground-500">{pick("正在加载图谱…", "Loading graph…")}</p>}>
        <DatasetGraphPanel datasetId={reference.datasetId ?? "demo-companies"} companyId={reference.companyId} depth={reference.depth} height={300} />
      </Suspense> : <p className="py-8 text-xs text-foreground-400">{pick("图谱进入可视区域后自动加载", "Graph loads when visible")}</p>}
    </div>
    <p className="text-xs leading-5 text-foreground-400">{pick(
      `生成时 ${reference.summary.nodeCount} 个节点、${reference.summary.edgeCount} 条关系。预览读取所选数据集当前关系，非模型预测贡献。`,
      `At creation: ${reference.summary.nodeCount} nodes, ${reference.summary.edgeCount} relationships. Preview loads current dataset relations, not model prediction contributions.`,
    )}</p>
  </section>;
}
