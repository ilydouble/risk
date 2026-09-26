import type { GraphData, NodeData } from "@antv/g6";
import { chartPalette } from "@/shared/config/theme/palette";
import type { GraphViewData } from "./types";

export function topologyKey({ nodes, edges, centerId }: GraphViewData): string {
  // Labels and presentation changes must not restart the layout or reset the viewport.
  return JSON.stringify([
    centerId,
    nodes.map(({ id }) => id).sort(),
    edges.map(({ id, source, target }) => [id, source, target]).sort(),
  ]);
}

export function toGraphData(data: GraphViewData, previous: NodeData[] = []): GraphData {
  const positions = new Map(previous.map(({ id, style }) => [id, style]));
  return {
    nodes: data.nodes.map((node) => {
      const color = node.color ?? chartPalette.primary;
      const position = positions.get(node.id);
      const selected = node.id === data.selectedId;
      return {
        id: node.id,
        style: {
          ...(position ? { x: position.x, y: position.y } : {}),
          size: node.size ?? (node.id === data.centerId ? 48 : 32),
          fill: color,
          fillOpacity: 0.16,
          stroke: color,
          lineWidth: selected ? 3 : 1.5,
          opacity: node.opacity ?? 1,
          halo: selected,
          haloStroke: color,
          haloLineWidth: 6,
          haloStrokeOpacity: 0.2,
          labelText: node.label,
          labelPlacement: "bottom",
          labelFontSize: 11,
          labelFill: chartPalette.secondary,
          labelWordWrap: true,
          labelMaxWidth: 150,
          labelMaxLines: 2,
          cursor: "grab",
        },
      };
    }),
    edges: data.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      style: {
        stroke: edge.color ?? chartPalette.axis,
        lineWidth: edge.width ?? 1.2,
        lineDash: edge.dashed ? [6, 6] : [],
        opacity: edge.opacity ?? 1,
        endArrow: true,
        labelText: edge.label ?? "",
        labelFontSize: 10,
        labelFill: edge.color ?? chartPalette.secondary,
        labelBackground: true,
        labelBackgroundFill: chartPalette.surface,
        labelBackgroundFillOpacity: 0.85,
      },
    })),
  };
}
