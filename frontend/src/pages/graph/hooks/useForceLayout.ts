import { useCallback, useEffect, useRef, useState } from "react";
import type { GraphEdge, GraphNode } from "@/entities/demo/model/types";

export interface Point {
  x: number;
  y: number;
}

interface SimNode extends Point {
  id: string;
  vx: number;
  vy: number;
  fixed: boolean;
}

const IDEAL_LENGTH = 156;
const REPULSION = 30000;
const SPRING = 0.02;
const GRAVITY = 0.0022;
const DAMPING = 0.82;
const COOLDOWN = 0.985;

/**
 * A compact force-directed simulation (repulsion + spring + gravity).
 * Runs synchronously over animation frames until the network cools down,
 * and supports pinning nodes while they are dragged.
 */
export function useForceLayout(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width: number,
  height: number,
) {
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const simRef = useRef<SimNode[]>([]);
  const [nonce, setNonce] = useState(0);

  const signature =
    nodes.map((node) => node.id).join("|") +
    "#" +
    edges.map((edge) => edge.id).join("|");

  useEffect(() => {
    if (!nodes.length || width <= 0 || height <= 0) return;

    const cx = width / 2;
    const cy = height / 2;

    const sim: SimNode[] = nodes.map((node, index) => {
      if (node.hop === 0) {
        return { id: node.id, x: cx, y: cy, vx: 0, vy: 0, fixed: true };
      }
      const angle =
        (index / Math.max(nodes.length - 1, 1)) * Math.PI * 2 + Math.PI / 6;
      const radius = 80 + node.hop * 92;
      return {
        id: node.id,
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
        fixed: false,
      };
    });

    simRef.current = sim;
    const index = new Map(sim.map((node) => [node.id, node]));
    const links = edges
      .filter((edge) => index.has(edge.source) && index.has(edge.target))
      .map((edge) => ({
        source: index.get(edge.source)!,
        target: index.get(edge.target)!,
        strength: edge.strength,
      }));

    let alpha = 1;
    let raf = 0;

    const step = () => {
      for (let i = 0; i < sim.length; i += 1) {
        for (let j = i + 1; j < sim.length; j += 1) {
          const a = sim[i];
          const b = sim[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          let dist2 = dx * dx + dy * dy;
          if (dist2 < 1) {
            dx = (Math.random() - 0.5) * 3;
            dy = (Math.random() - 0.5) * 3;
            dist2 = dx * dx + dy * dy;
          }
          const dist = Math.sqrt(dist2);
          const force = REPULSION / dist2;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          a.vx -= fx;
          a.vy -= fy;
          b.vx += fx;
          b.vy += fy;
        }
      }

      links.forEach(({ source, target, strength }) => {
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (dist - IDEAL_LENGTH) * SPRING * strength;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        source.vx += fx;
        source.vy += fy;
        target.vx -= fx;
        target.vy -= fy;
      });

      sim.forEach((node) => {
        if (node.fixed) return;
        node.vx += (cx - node.x) * GRAVITY;
        node.vy += (cy - node.y) * GRAVITY;
      });

      sim.forEach((node) => {
        if (node.fixed) {
          node.vx = 0;
          node.vy = 0;
          return;
        }
        node.vx *= DAMPING;
        node.vy *= DAMPING;
        node.x += node.vx * alpha;
        node.y += node.vy * alpha;
        node.x = Math.max(56, Math.min(width - 56, node.x));
        node.y = Math.max(48, Math.min(height - 48, node.y));
      });

      alpha *= COOLDOWN;
    };

    const frame = () => {
      for (let k = 0; k < 2; k += 1) step();
      const next: Record<string, Point> = {};
      sim.forEach((node) => {
        next[node.id] = { x: node.x, y: node.y };
      });
      setPositions(next);
      if (alpha > 0.03) {
        raf = requestAnimationFrame(frame);
      }
    };

    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, width, height, nonce]);

  const moveNode = useCallback((id: string, x: number, y: number) => {
    const node = simRef.current.find((item) => item.id === id);
    if (!node) return;
    node.x = x;
    node.y = y;
    node.vx = 0;
    node.vy = 0;
    setPositions((prev) => ({ ...prev, [id]: { x, y } }));
  }, []);

  const pinNode = useCallback((id: string, fixed: boolean) => {
    const node = simRef.current.find((item) => item.id === id);
    if (node) node.fixed = fixed;
  }, []);

  const relayout = useCallback(() => setNonce((value) => value + 1), []);

  return { positions, moveNode, pinNode, relayout };
}