import { useTranslation } from "react-i18next";
import Card from "@/components/base/Card";
import { riskColor } from "@/pages/graph/lib/graph";
import type { RiskPath } from "@/types";

interface RiskPathPanelProps {
  paths: RiskPath[];
  onSelectNode: (id: string) => void;
  focusRisk: boolean;
  onToggleFocusRisk: () => void;
}

export default function RiskPathPanel({
  paths,
  onSelectNode,
  focusRisk,
  onToggleFocusRisk,
}: RiskPathPanelProps) {
  const { t } = useTranslation();
  const highPaths = paths.filter((path) => path.riskLevel === "high");

  return (
    <Card
      title={t("graph.path.title")}
      subtitle={t("graph.path.subtitle")}
      icon="ri-route-line"
      bodyClassName="p-4"
      action={
        <button
          type="button"
          onClick={onToggleFocusRisk}
          className={`flex cursor-pointer items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-1 text-[10px] transition-colors ${
            focusRisk
              ? "border-accent-500/50 bg-accent-500/15 text-accent-400"
              : "border-background-300 text-foreground-500 hover:text-foreground-900"
          }`}
        >
          <i className="ri-focus-mode text-[12px]"></i>
          {focusRisk ? t("graph.path.focused") : t("graph.path.focus")}
        </button>
      }
    >
      {paths.length === 0 ? (
        <p className="rounded-md border border-dashed border-background-300 bg-background-50 p-4 text-center text-[11px] text-foreground-500">
          {t("graph.path.empty")}
        </p>
      ) : (
        <ul className="space-y-2.5">
          {paths.map((path) => (
            <li
              key={path.nodeId}
              className="rounded-md border border-background-200/70 bg-background-50 p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex min-w-0 items-center gap-1.5">
                  <span
                    className="h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ backgroundColor: riskColor[path.riskLevel] }}
                  ></span>
                  <span className="truncate text-[12px] font-medium text-foreground-900">
                    {path.label}
                  </span>
                </div>
                <span className="shrink-0 whitespace-nowrap rounded-full bg-background-200/80 px-2 py-0.5 font-mono text-[10px] text-foreground-600">
                  {t("graph.path.hops", { count: path.hops })}
                </span>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-1">
                {path.chain.map((label, index) => (
                  <span key={`${path.nodeId}-${index}`} className="flex items-center gap-1">
                    <span className="max-w-[96px] truncate rounded bg-background-200/70 px-1.5 py-0.5 text-[10px] text-foreground-700">
                      {label}
                    </span>
                    {index < path.chain.length - 1 && (
                      <i className="ri-arrow-right-s-line text-[12px] text-foreground-500"></i>
                    )}
                  </span>
                ))}
              </div>

              <button
                type="button"
                onClick={() => onSelectNode(path.nodeId)}
                className="mt-2 flex cursor-pointer items-center gap-1 whitespace-nowrap text-[11px] text-primary-400 transition-colors hover:text-primary-300"
              >
                <i className="ri-crosshair-2-line text-[13px]"></i>
                {t("graph.path.locate")}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex items-start gap-2 rounded-md border border-background-200/70 bg-background-50 p-3">
        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center text-accent-400">
          <i className="ri-lightbulb-line text-[14px]"></i>
        </span>
        <p className="text-[11px] leading-relaxed text-foreground-600">
          {t("graph.path.tip", { count: highPaths.length })}
        </p>
      </div>
    </Card>
  );
}