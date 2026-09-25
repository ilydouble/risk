export default {
  overview: {
    title: "Overview",
    subtitle:
      "Global corporate credit coverage, real-time risk assessment monitoring and system status",
    actions: {
      batch: "Batch",
      newEval: "New evaluation",
      viewAll: "View all",
      modelCard: "Model card",
    },
    ranges: {
      d7: "Last 7 days",
      d14: "Last 14 days",
    },
    stats: {
      covered: "Companies covered",
      coveredDelta: "+3.2% MoM",
      today: "Evaluations today",
      todayDelta: "+128 vs yesterday",
      highRisk: "High-risk companies",
      highRiskDelta: "+12 in 7 days",
      avgScore: "Avg. credit score",
      avgScoreUnit: "/ 1000",
      avgDelta: "-4 vs last quarter",
    },
    chart: {
      trendTitle: "Evaluation & high-risk trend",
      trendSubtitle: "Daily evaluation requests and high-risk identifications",
      seriesEvaluations: "Evaluations",
      seriesHighRisk: "High risk",
    },
    risk: {
      title: "Risk distribution",
      subtitle: "Share of covered companies by risk level",
      centerLabel: "Companies covered",
      low: "Low risk",
      medium: "Medium risk",
      high: "High risk",
    },
    system: {
      title: "System status",
      subtitle: "Core service health and response latency",
    },
    recent: {
      title: "Recently evaluated",
      subtitle: "Latest completed credit assessments",
      colCompany: "Company",
      colScore: "Score",
      colPd: "Default prob.",
      colRisk: "Risk level",
      colAction: "Action",
      viewScore: "Score details",
    },
    model: {
      title: "Core model metrics",
      subtitle: "v4.2 offline validation results",
      metrics: {
        auc: "vs prev +0.016",
        ks: "vs prev +0.021",
        lift: "vs prev +0.14",
        brier: "vs prev -0.007",
      },
    },
    demo: {
      active: "Demo mode is on",
      desc: "Loaded masked demo data and 3 preset cases. You can walk through the full credit assessment flow.",
    },
    services: {
      scoring: { name: "Scoring demo", desc: "Seeded score snapshots · no live inference" },
      graph: { name: "Knowledge graph query", desc: "2–3 hop relation search & propagation" },
      credit: { name: "Overseas credit sources", desc: "12 country data sources in sync" },
      report: { name: "Report generation engine", desc: "Streaming body + citation assembly" },
    },
    preset: {
      PC01: {
        title: "Stable · Core precision-manufacturing supplier",
        summary: "Low risk. Recommend a large long-term limit with an extended payment term.",
      },
      PC02: {
        title: "Watch · Controller change + related-party guarantee",
        summary: "Medium risk. Recommend a shorter term with added collateral and guarantee clauses.",
      },
      PC03: {
        title: "Alert · Multiple lawsuits and overdue payments",
        summary: "High risk. Recommend rejection or settlement via letter of credit only.",
      },
    },
  },
};
