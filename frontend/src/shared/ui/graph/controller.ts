import { CanvasEvent, Graph, NodeEvent, type IElementEvent } from "@antv/g6";
import { toGraphData, topologyKey } from "./data";
import type { GraphViewData } from "./types";

export type GraphStatus = "loading" | "ready" | "error";

export function createGraphController(
  container: HTMLDivElement,
  onSelect: (id: string | null) => void,
  onStatus: (status: GraphStatus) => void,
) {
  // Each effect owns its mount, so a pending render cannot attach to a newer StrictMode mount.
  const mount = document.createElement("div");
  container.append(mount);
  let graph: Graph | undefined;
  let disposed = false;
  let failed = false;
  let pending: GraphViewData | undefined;
  let appliedTopology: string | undefined;
  let needsFit = false;
  let processing = false;
  let queue = Promise.resolve();

  const fail = (error: unknown) => {
    if (disposed || failed) return;
    failed = true;
    console.error("Graph rendering failed", error);
    onStatus("error");
  };

  const enqueue = (operation: () => Promise<void>) => {
    queue = queue.then(async () => {
      if (!disposed && !failed) await operation();
    }).catch(fail);
  };

  const fit = async () => {
    if (graph?.rendered && graph.getNodeData().length) {
      await graph.fitView({ when: "always" }, false);
    }
  };

  const flush = () => {
    if (processing || !pending || disposed || failed) return;
    processing = true;
    enqueue(async () => {
      try {
        while (pending && !disposed) {
          const width = container.clientWidth;
          const height = container.clientHeight;
          if (!width || !height) break;
          const data = pending;
          pending = undefined;
          if (!graph) {
            graph = new Graph({
              container: mount,
              width,
              height,
              autoResize: false,
              animation: false,
              padding: 44,
              zoomRange: [0.1, 4],
              node: { type: "circle" },
              // Leave edge.type unset: the parallel-edge transform selects curved edge shapes.
              transforms: [{ type: "process-parallel-edges", mode: "bundle", distance: 20 }],
              layout: {
                type: "d3-force",
                animation: true,
                alphaDecay: 0.12,
                link: { distance: 150 },
                manyBody: { strength: -400 },
                collide: { radius: 40 },
              },
              behaviors: ["drag-canvas", "zoom-canvas", "drag-element-force"],
            });
            graph.on(NodeEvent.CLICK, (event: IElementEvent) => onSelect(event.target.id));
            graph.on(CanvasEvent.CLICK, () => onSelect(null));
          }
          const topology = topologyKey(data);
          const changed = topology !== appliedTopology;
          graph.setData(toGraphData(data, changed ? [] : graph.getNodeData()));
          if (changed) {
            needsFit = true;
            onStatus("loading");
            await graph.render();
          } else {
            await graph.draw();
          }
          if (disposed) break;
          appliedTopology = topology;
          if (needsFit && !pending) {
            await fit();
            needsFit = false;
          }
          if (!disposed) onStatus("ready");
        }
      } finally {
        processing = false;
      }
    });
  };

  const observer = new ResizeObserver(() => {
    enqueue(async () => {
      if (!graph || !container.clientWidth || !container.clientHeight) return;
      graph.setSize(container.clientWidth, container.clientHeight);
    });
    flush();
  });
  observer.observe(container);

  return {
    update(data: GraphViewData) {
      pending = data;
      flush();
    },
    zoom(ratio: number) {
      enqueue(async () => {
        if (graph?.rendered) await graph.zoomBy(ratio, false);
      });
    },
    reset() {
      enqueue(fit);
    },
    dispose() {
      disposed = true;
      observer.disconnect();
      mount.remove();
      // G6 render/draw are asynchronous. Destroy only after the active operation settles.
      void queue.finally(() => graph?.destroy());
    },
  };
}
