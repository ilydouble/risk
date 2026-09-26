import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { edgeTypeMeta, riskColor } from "@/features/demo-scenarios/lib/graph";
import type { GraphEdge, GraphNode } from "@/entities/demo/model/types";
import { GraphView } from "@/shared/ui/graph";

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  focusRisk: boolean;
  onRiskPath: Set<string>;
  height?: number;
}

export default function GraphCanvas({
  nodes, edges, selectedId, onSelect, focusRisk, onRiskPath, height = 620,
}: GraphCanvasProps) {
  const { t } = useTranslation();
  const data = useMemo(() => ({
    nodes: nodes.map((node) => ({
      id: node.id,
      label: node.label,
      color: riskColor[node.riskLevel],
      opacity: focusRisk && node.hop !== 0 && !onRiskPath.has(node.id) ? 0.22 : 1,
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: selectedId === edge.source || selectedId === edge.target ? edge.label : "",
      color: edge.riskFlow ? riskColor.high : edgeTypeMeta[edge.type].color,
      dashed: edge.riskFlow || edgeTypeMeta[edge.type].dashed,
      width: edge.riskFlow ? 2 : 1.2,
      opacity: focusRisk && !edge.riskFlow ? 0.1 : edge.riskFlow ? 0.95 : 0.55,
    })),
  }), [nodes, edges, selectedId, focusRisk, onRiskPath]);

  return (
    <GraphView
      {...data}
      centerId={nodes.find((node) => node.hop === 0)?.id}
      selectedId={selectedId}
      onSelect={onSelect}
      height={height}
      ariaLabel={t("graph.network.title")}
    />
  );
}
