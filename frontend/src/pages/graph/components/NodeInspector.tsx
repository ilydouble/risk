import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Card from "@/shared/ui/Card";
import RiskBadge from "@/entities/risk/ui/RiskBadge";
import { useLang } from "@/shared/lib/useLang";
import { nodeTypeMeta, riskColor } from "@/features/demo-scenarios/lib/graph";
import type { GraphEdge, GraphNode } from "@/entities/demo/model/types";

interface NodeInspectorProps {
  node: GraphNode | null;
  rootId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelect: (id: string) => void;
  onDrill: (companyId: string) => void;
  onExpand: () => void;
}

export default function NodeInspector({
  node,
  rootId,
  nodes,
  edges,
  onSelect,
  onDrill,
  onExpand,
}: NodeInspectorProps) {
  const { t } = useTranslation();
  const { isEn } = useLang();

  if (!node) {
    return (
      <Card
        title={t("graph.inspector.title")}
        subtitle={t("graph.inspector.emptySubtitle")}
        icon="ri-focus-3-line"
        bodyClassName="p-4"
      >
        <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-background-300 bg-background-50 px-4 py-8 text-center">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-background-200 text-foreground-500">
            <i className="ri-cursor-line text-lg"></i>
          </span>
          <p className="mt-3 text-xs text-foreground-500">
            {t("graph.inspector.empty")}
          </p>
        </div>
      </Card>
    );
  }

  const neighbors = edges
    .filter((edge) => edge.source === node.id || edge.target === node.id)
    .map((edge) => {
      const otherId = edge.source === node.id ? edge.target : edge.source;
      return {
        edge,
        node: nodes.find((item) => item.id === otherId),
      };
    })
    .filter((item): item is { edge: GraphEdge; node: GraphNode } =>
      Boolean(item.node),
    );

  const meta = nodeTypeMeta[node.type];
  const color = riskColor[node.riskLevel];

  const fields = [
    { label: t("graph.inspector.nodeType"), value: isEn ? meta.labelEn : meta.label },
    { label: t("graph.inspector.relation"), value: node.relation },
    { label: t("graph.inspector.exposure"), value: node.exposure },
    { label: t("graph.inspector.country"), value: node.country ?? "—" },
    { label: t("graph.inspector.industry"), value: node.industry ?? "—" },
    {
      label: t("graph.inspector.hop"),
      value:
        node.hop === 0
          ? t("graph.inspector.root")
          : t("graph.inspector.hopValue", { count: node.hop }),
    },
  ];

  return (
    <Card
      title={t("graph.inspector.title")}
      subtitle={t("graph.inspector.subtitle")}
      icon="ri-focus-3-line"
      bodyClassName="p-4"
      action={<RiskBadge level={node.riskLevel} size="sm" />}
    >
      <div className="flex items-start gap-3">
        <span
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
          style={{ backgroundColor: `${color}1f` }}
        >
          <i className={`${meta.icon} text-lg`} style={{ color }}></i>
        </span>
        <div className="min-w-0">
          <p className="text-[13px] font-semibold leading-snug text-foreground-950">
            {node.label}
          </p>
          <p className="mt-0.5 font-mono text-[11px] text-foreground-500">
            {node.id}
          </p>
        </div>
      </div>

      {node.note && (
        <p className="mt-3 rounded-md border border-background-200/70 bg-background-50 p-3 text-[11px] leading-relaxed text-foreground-600">
          {node.note}
        </p>
      )}

      <dl className="mt-3 grid grid-cols-2 gap-2">
        {fields.map((field) => (
          <div
            key={field.label}
            className="rounded-md border border-background-200/70 bg-background-50 px-2.5 py-2"
          >
            <dt className="text-[10px] text-foreground-500">{field.label}</dt>
            <dd className="mt-0.5 truncate text-[12px] text-foreground-900">
              {field.value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="mt-3">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-medium text-foreground-700">
            {t("graph.inspector.direct", { count: neighbors.length })}
          </p>
        </div>
        <ul className="mt-2 space-y-1.5">
          {neighbors.slice(0, 5).map(({ edge, node: neighbor }) => (
            <li key={edge.id}>
              <button
                type="button"
                onClick={() => onSelect(neighbor.id)}
                className="flex w-full cursor-pointer items-center gap-2 rounded-md border border-background-200/70 bg-background-50 px-2.5 py-2 text-left transition-colors hover:border-primary-400/60"
              >
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ backgroundColor: riskColor[neighbor.riskLevel] }}
                ></span>
                <span className="min-w-0 flex-1 truncate text-[11px] text-foreground-800">
                  {neighbor.label}
                </span>
                <span className="shrink-0 whitespace-nowrap text-[10px] text-foreground-500">
                  {edge.riskFlow ? t("graph.inspector.riskFlow") : edge.label}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {node.companyId && node.companyId !== rootId && (
          <>
            <Link
              to={`/company/${node.companyId}`}
              className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-background-300 px-3 py-2 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
            >
              <i className="ri-profile-line text-sm"></i>
              {t("graph.inspector.viewProfile")}
            </Link>
            <button
              type="button"
              onClick={() => onDrill(node.companyId!)}
              className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-primary-500 px-3 py-2 text-[11px] font-medium text-background-50 transition-colors hover:bg-primary-600"
            >
              <i className="ri-focus-2-line text-sm"></i>
              {t("graph.inspector.focusCenter")}
            </button>
          </>
        )}
        {node.hop > 0 && node.hop < 3 && (
          <button
            type="button"
            onClick={onExpand}
            className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md border border-accent-500/50 bg-accent-500/12 px-3 py-2 text-[11px] text-accent-400 transition-colors hover:bg-accent-500/20"
          >
            <i className="ri-node-tree text-sm"></i>
            {t("graph.inspector.drill")}
          </button>
        )}
      </div>
    </Card>
  );
}