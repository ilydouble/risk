import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { useTranslation } from "react-i18next";
import { edgeTypeMeta, nodeTypeMeta, riskColor } from "@/pages/graph/lib/graph";
import { useForceLayout } from "@/pages/graph/hooks/useForceLayout";
import type { GraphEdge, GraphNode } from "@/types";

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  focusRisk: boolean;
  onRiskPath: Set<string>;
  height?: number;
}

interface DragState {
  mode: "pan" | "node";
  id?: string;
  startX: number;
  startY: number;
  panX: number;
  panY: number;
  moved: boolean;
}

const ZOOM_MIN = 0.55;
const ZOOM_MAX = 1.9;

export default function GraphCanvas({
  nodes,
  edges,
  selectedId,
  onSelect,
  focusRisk,
  onRiskPath,
  height = 620,
}: GraphCanvasProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const dragRef = useRef<DragState | null>(null);

  const { positions, moveNode, pinNode, relayout } = useForceLayout(
    nodes,
    edges,
    width,
    height,
  );

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      entries.forEach((entry) => setWidth(entry.contentRect.width));
    });
    observer.observe(element);
    setWidth(element.clientWidth);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      setZoom((value) => {
        const next = value * (event.deltaY < 0 ? 1.08 : 0.92);
        return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, next));
      });
    };
    element.addEventListener("wheel", handleWheel, { passive: false });
    return () => element.removeEventListener("wheel", handleWheel);
  }, []);

  const resetView = () => {
    setPan({ x: 0, y: 0 });
    setZoom(1);
    relayout();
  };

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedId) ?? null,
    [nodes, selectedId],
  );

  const handlePointerDown = (event: ReactPointerEvent) => {
    dragRef.current = {
      mode: "pan",
      startX: event.clientX,
      startY: event.clientY,
      panX: pan.x,
      panY: pan.y,
      moved: false,
    };
  };

  const handleNodePointerDown = (
    event: ReactPointerEvent,
    nodeId: string,
  ) => {
    event.stopPropagation();
    pinNode(nodeId, true);
    dragRef.current = {
      mode: "node",
      id: nodeId,
      startX: event.clientX,
      startY: event.clientY,
      panX: pan.x,
      panY: pan.y,
      moved: false,
    };
  };

  const handlePointerMove = (event: ReactPointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) drag.moved = true;

    if (drag.mode === "pan") {
      setPan({ x: drag.panX + dx, y: drag.panY + dy });
    } else if (drag.id && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const x = (event.clientX - rect.left - pan.x) / zoom;
      const y = (event.clientY - rect.top - pan.y) / zoom;
      moveNode(drag.id, x, y);
    }
  };

  const handlePointerUp = () => {
    const drag = dragRef.current;
    if (drag?.mode === "node" && drag.id) {
      pinNode(drag.id, false);
      if (!drag.moved) onSelect(drag.id);
    } else if (drag && !drag.moved) {
      onSelect(null);
    }
    dragRef.current = null;
  };

  const transform = `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`;

  return (
    <div
      ref={containerRef}
      className="tech-grid relative w-full touch-none select-none overflow-hidden rounded-lg bg-background-50"
      style={{ height }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
    >
      {width > 0 && (
        <>
          <svg
            width={width}
            height={height}
            className="absolute left-0 top-0"
            style={{ transform, transformOrigin: "0 0" }}
          >
            <defs>
              <marker
                id="graph-arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#a9aebd" />
              </marker>
              <marker
                id="graph-arrow-risk"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path
                  d="M 0 0 L 10 5 L 0 10 z"
                  fill={riskColor.high}
                />
              </marker>
            </defs>

            {edges.map((edge) => {
              const from = positions[edge.source];
              const to = positions[edge.target];
              if (!from || !to) return null;
              const meta = edgeTypeMeta[edge.type];
              const onPath = edge.riskFlow;
              const dimmed = focusRisk && !onPath;
              const midX = (from.x + to.x) / 2;
              const midY = (from.y + to.y) / 2;
              const touchSelected =
                selectedId === edge.source || selectedId === edge.target;
              const stroke = onPath ? riskColor.high : meta.color;

              return (
                <g
                  key={edge.id}
                  style={{ opacity: dimmed ? 0.1 : 1 }}
                  className="transition-opacity"
                >
                  <line
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke={stroke}
                    strokeWidth={onPath ? 2 : 1.2}
                    strokeDasharray={
                      onPath ? "6 6" : meta.dashed ? "4 4" : undefined
                    }
                    strokeLinecap="round"
                    className={onPath ? "animate-dash-flow" : undefined}
                    markerEnd={
                      onPath ? "url(#graph-arrow-risk)" : "url(#graph-arrow)"
                    }
                    style={{ opacity: onPath ? 0.95 : 0.55 }}
                  />
                  {touchSelected && (
                    <text
                      x={midX}
                      y={midY - 5}
                      textAnchor="middle"
                      className="font-mono"
                      style={{
                        fill: stroke,
                        fontSize: 10,
                        paintOrder: "stroke",
                        stroke: "oklch(var(--background-50))",
                        strokeWidth: 3,
                      }}
                    >
                      {edge.label}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          <div
            className="absolute left-0 top-0"
            style={{
              transform,
              transformOrigin: "0 0",
              width,
              height,
            }}
          >
            {nodes.map((node) => {
              const point = positions[node.id];
              if (!point) return null;
              const color = riskColor[node.riskLevel];
              const isRoot = node.hop === 0;
              const isSelected = node.id === selectedId;
              const isHovered = node.id === hoveredId;
              const dimmed = focusRisk && !isRoot && !onRiskPath.has(node.id);
              const size = isRoot ? 62 : 46;
              const iconSize = isRoot ? 26 : 19;
              const showLabel =
                isRoot || isSelected || isHovered || node.riskLevel === "high";

              return (
                <button
                  key={node.id}
                  type="button"
                  onPointerDown={(event) => handleNodePointerDown(event, node.id)}
                  onPointerEnter={() => setHoveredId(node.id)}
                  onPointerLeave={() =>
                    setHoveredId((current) =>
                      current === node.id ? null : current,
                    )
                  }
                  className="absolute -translate-x-1/2 -translate-y-1/2 cursor-grab active:cursor-grabbing"
                  style={{
                    left: point.x,
                    top: point.y,
                    opacity: dimmed ? 0.22 : 1,
                  }}
                >
                  <span
                    className="flex items-center justify-center rounded-full border-2 transition-transform"
                    style={{
                      width: size,
                      height: size,
                      borderColor: color,
                      backgroundColor: `${color}24`,
                      boxShadow: isSelected
                        ? `0 0 0 4px ${color}38`
                        : isHovered
                          ? `0 0 0 3px ${color}22`
                          : "none",
                    }}
                  >
                    <i
                      className={`${nodeTypeMeta[node.type].icon}`}
                      style={{ color, fontSize: iconSize }}
                    ></i>
                  </span>
                  <span
                    className={`absolute left-1/2 top-full mt-1 block max-w-[112px] -translate-x-1/2 truncate whitespace-nowrap rounded border border-background-200/70 bg-background-100/90 px-1.5 py-0.5 text-center text-[10px] transition-opacity ${
                      isSelected ? "text-foreground-950" : "text-foreground-700"
                    }`}
                    style={{ opacity: showLabel ? 1 : 0 }}
                  >
                    {node.label}
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}

      <div className="pointer-events-none absolute bottom-3 left-3 flex items-center gap-1.5 rounded-md border border-background-300/70 bg-background-100/85 px-2 py-1 font-mono text-[10px] text-foreground-500">
        <i className="ri-drag-move-2-line text-[12px]"></i>
        {t("graph.canvas.hint")}
      </div>

      <div className="absolute bottom-3 right-3 flex items-center gap-1.5">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            setZoom((value) => Math.min(ZOOM_MAX, value + 0.15));
          }}
          onPointerDown={(event) => event.stopPropagation()}
          className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-md border border-background-300 bg-background-100/85 text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
          title={t("graph.canvas.zoomIn")}
        >
          <i className="ri-add-line text-[15px]"></i>
        </button>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            setZoom((value) => Math.max(ZOOM_MIN, value - 0.15));
          }}
          onPointerDown={(event) => event.stopPropagation()}
          className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-md border border-background-300 bg-background-100/85 text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
          title={t("graph.canvas.zoomOut")}
        >
          <i className="ri-subtract-line text-[15px]"></i>
        </button>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            resetView();
          }}
          onPointerDown={(event) => event.stopPropagation()}
          className="flex h-8 cursor-pointer items-center gap-1 whitespace-nowrap rounded-md border border-background-300 bg-background-100/85 px-2.5 text-[11px] text-foreground-700 transition-colors hover:border-primary-400 hover:text-primary-400"
        >
          <i className="ri-restart-line text-[14px]"></i>
          {t("graph.canvas.reset")}
        </button>
      </div>

      {selectedNode && (
        <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-md border border-background-300/70 bg-background-100/90 px-2.5 py-1.5">
          <span
            className="flex h-5 w-5 items-center justify-center rounded-full"
            style={{ backgroundColor: `${riskColor[selectedNode.riskLevel]}24` }}
          >
            <i
              className={`${nodeTypeMeta[selectedNode.type].icon} text-[12px]`}
              style={{ color: riskColor[selectedNode.riskLevel] }}
            ></i>
          </span>
          <span className="max-w-[220px] truncate text-[11px] text-foreground-900">
            {selectedNode.label}
          </span>
        </div>
      )}
    </div>
  );
}