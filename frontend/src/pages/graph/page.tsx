import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import AppShell from "@/components/feature/AppShell";
import Card from "@/components/base/Card";
import RiskBadge from "@/components/base/RiskBadge";
import GraphToolbar from "@/pages/graph/components/GraphToolbar";
import GraphCanvas from "@/pages/graph/components/GraphCanvas";
import GraphLegend from "@/pages/graph/components/GraphLegend";
import NodeInspector from "@/pages/graph/components/NodeInspector";
import RiskPathPanel from "@/pages/graph/components/RiskPathPanel";
import { applyRiskTransmission, buildGraphData } from "@/pages/graph/lib/graph";
import { resolveProfile } from "@/pages/company/lib/profile";
import { useLang } from "@/hooks/useLang";
import { companies } from "@/mocks/companies";
import { DEFAULT_GRAPH_COMPANY_ID } from "@/constants/nav";
import type { GraphEdgeType, GraphNodeType } from "@/types";

export default function GraphPage() {
  const { t } = useTranslation();
  const { isEn, lang } = useLang();
  const [searchParams, setSearchParams] = useSearchParams();
  const companyId = searchParams.get("company") ?? DEFAULT_GRAPH_COMPANY_ID;

  const companyOptions = useMemo(
    () =>
      companies.map((company) => ({
        value: company.id,
        label: isEn ? company.nameEn : company.nameCn,
      })),
    [isEn],
  );

  const company = useMemo(
    () =>
      companies.find((item) => item.id === companyId) ??
      companies.find((item) => item.id === DEFAULT_GRAPH_COMPANY_ID)!,
    [companyId],
  );

  const graph = useMemo(
    () => buildGraphData(companies, company, resolveProfile(company), lang),
    [company, lang],
  );

  const paths = useMemo(() => applyRiskTransmission(graph), [graph]);

  const [depth, setDepth] = useState(3);
  const [focusRisk, setFocusRisk] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedId(null);
    setFocusRisk(false);
  }, [company.id]);

  const visibleNodes = useMemo(
    () => graph.nodes.filter((node) => node.hop <= depth),
    [graph, depth],
  );

  const visibleIds = useMemo(
    () => new Set(visibleNodes.map((node) => node.id)),
    [visibleNodes],
  );

  const visibleEdges = useMemo(
    () =>
      graph.edges.filter(
        (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
      ),
    [graph, visibleIds],
  );

  const riskPathNodes = useMemo(() => {
    const set = new Set<string>();
    graph.edges
      .filter((edge) => edge.riskFlow)
      .forEach((edge) => {
        set.add(edge.source);
        set.add(edge.target);
      });
    return set;
  }, [graph]);

  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedId) ?? null,
    [graph, selectedId],
  );

  const nodeTypes = useMemo(() => {
    const set = new Set<GraphNodeType>();
    visibleNodes.forEach((node) => set.add(node.type));
    return Array.from(set);
  }, [visibleNodes]);

  const edgeTypes = useMemo(() => {
    const set = new Set<GraphEdgeType>();
    visibleEdges.forEach((edge) => set.add(edge.type));
    return Array.from(set);
  }, [visibleEdges]);

  const relatedCount = visibleNodes.filter((node) => node.hop > 0).length;
  const highRiskCount = graph.nodes.filter(
    (node) => node.hop > 0 && node.riskLevel === "high",
  ).length;
  const riskPathCount = paths.filter((path) => path.riskLevel === "high").length;

  const stats = [
    {
      label: t("graph.stats.related"),
      unit: t("graph.stats.relatedUnit"),
      value: String(relatedCount),
      icon: "ri-node-tree",
      tone: "text-primary-400",
    },
    {
      label: t("graph.stats.highRisk"),
      unit: t("graph.stats.highRiskUnit"),
      value: String(highRiskCount),
      icon: "ri-alert-line",
      tone: "text-accent-400",
    },
    {
      label: t("graph.stats.paths"),
      unit: t("graph.stats.pathsUnit"),
      value: String(riskPathCount),
      icon: "ri-route-line",
      tone: "text-accent-400",
    },
    {
      label: t("graph.stats.edges"),
      unit: t("graph.stats.edgesUnit"),
      value: String(visibleEdges.length),
      icon: "ri-share-forward-line",
      tone: "text-foreground-900",
    },
  ];

  const infoItems = [
    {
      icon: "ri-focus-2-line",
      title: t("graph.info.centerTitle"),
      desc: t("graph.info.centerDesc"),
    },
    {
      icon: "ri-route-line",
      title: t("graph.info.pathTitle"),
      desc: t("graph.info.pathDesc"),
    },
    {
      icon: "ri-node-tree",
      title: t("graph.info.drillTitle"),
      desc: t("graph.info.drillDesc"),
    },
  ];

  const handleCompanyChange = (id: string) => {
    setSearchParams({ company: id });
  };

  const handleDrill = (id: string) => {
    setSearchParams({ company: id });
    setDepth(3);
  };

  return (
    <AppShell
      title={t("graph.title")}
      subtitle={t("graph.subtitle")}
      companyId={company.id}
    >
      <div className="space-y-4">
        <section className="animate-fade-up flex flex-col gap-3 rounded-lg border border-background-200 bg-background-100 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary-500/12 text-primary-400">
              <i className="ri-building-2-line text-xl"></i>
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-heading text-[15px] font-semibold text-foreground-950">
                  {isEn ? company.nameEn : company.nameCn}
                </h2>
                <RiskBadge level={company.riskLevel} size="sm" />
                <span className="rounded-full bg-background-200/80 px-2 py-0.5 font-mono text-[10px] text-foreground-600">
                  {company.region} · {company.sector}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-foreground-500">
                {t("graph.snapshot", { date: company.updatedAt })}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:w-[440px]">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-md border border-background-200 bg-background-50 px-3 py-2"
              >
                <div className="flex items-center gap-1.5">
                  <span className="flex h-4 w-4 items-center justify-center text-foreground-500">
                    <i className={`${stat.icon} text-[13px]`}></i>
                  </span>
                  <span className="truncate text-[10px] text-foreground-500">
                    {stat.label}
                  </span>
                </div>
                <p className="mt-1 flex items-baseline gap-1">
                  <span
                    className={`font-mono text-base font-semibold ${stat.tone}`}
                  >
                    {stat.value}
                  </span>
                  {stat.unit && (
                    <span className="text-[10px] text-foreground-500">
                      {stat.unit}
                    </span>
                  )}
                </p>
              </div>
            ))}
          </div>
        </section>

        <div className="animate-fade-up" style={{ animationDelay: "40ms" }}>
          <GraphToolbar
            companyOptions={companyOptions}
            companyId={company.id}
            onCompanyChange={handleCompanyChange}
            depth={depth}
            onDepthChange={setDepth}
            focusRisk={focusRisk}
            onToggleFocusRisk={() => setFocusRisk((value) => !value)}
            riskPathCount={riskPathCount}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-4">
            <Card
              title={t("graph.network.title")}
              subtitle={t("graph.network.subtitle", {
                depth,
                count: visibleNodes.length,
              })}
              icon="ri-node-tree"
              bodyClassName="p-0"
              className="animate-fade-up"
              action={
                <span className="whitespace-nowrap rounded-full bg-background-200/80 px-2.5 py-1 font-mono text-[10px] text-foreground-600">
                  {t("graph.network.badge")}
                </span>
              }
            >
              <div className="p-3">
                <GraphCanvas
                  nodes={visibleNodes}
                  edges={visibleEdges}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  focusRisk={focusRisk}
                  onRiskPath={riskPathNodes}
                  height={620}
                />
              </div>
            </Card>

            <div className="animate-fade-up" style={{ animationDelay: "80ms" }}>
              <GraphLegend nodeTypes={nodeTypes} edgeTypes={edgeTypes} />
            </div>
          </div>

          <div className="space-y-4">
            <div className="animate-fade-up" style={{ animationDelay: "60ms" }}>
              <NodeInspector
                node={selectedNode}
                rootId={graph.rootId}
                nodes={graph.nodes}
                edges={graph.edges}
                onSelect={setSelectedId}
                onDrill={handleDrill}
                onExpand={() => setDepth((value) => Math.min(3, value + 1))}
              />
            </div>
            <div className="animate-fade-up" style={{ animationDelay: "100ms" }}>
              <RiskPathPanel
                paths={paths}
                onSelectNode={setSelectedId}
                focusRisk={focusRisk}
                onToggleFocusRisk={() => setFocusRisk((value) => !value)}
              />
            </div>
            <div className="animate-fade-up" style={{ animationDelay: "140ms" }}>
              <Card
                title={t("graph.info.title")}
                subtitle={t("graph.info.subtitle")}
                icon="ri-information-line"
                bodyClassName="p-4"
              >
                <ul className="space-y-2.5">
                  {infoItems.map((item) => (
                    <li key={item.title} className="flex items-start gap-2.5">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-secondary-500/12 text-secondary-300">
                        <i className={`${item.icon} text-[14px]`}></i>
                      </span>
                      <div>
                        <p className="text-[12px] font-medium text-foreground-900">
                          {item.title}
                        </p>
                        <p className="mt-0.5 text-[11px] leading-relaxed text-foreground-500">
                          {item.desc}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 rounded-md border border-background-200/70 bg-background-50 p-2.5 text-[10px] text-foreground-500">
                  {t("graph.info.footer", {
                    risk: t(`risk.${company.riskLevel}`),
                  })}
                </p>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}