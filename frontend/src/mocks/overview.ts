import type {
  ModelMetric,
  OverviewStats,
  PresetCase,
  RiskDistributionItem,
  SystemService,
  TrendPoint,
} from "@/types";

export const overviewStats: OverviewStats = {
  coveredCompanies: 12864,
  coveredDelta: "+3.2% 环比",
  todayEvaluations: 1462,
  todayDelta: "+128 较昨日",
  highRiskCount: 386,
  highRiskDelta: "+12 近 7 天",
  avgCreditScore: 697,
  avgDelta: "-4 较上季",
};

export const evaluationTrend: TrendPoint[] = [
  { date: "09-11", evaluations: 986, highRisk: 42 },
  { date: "09-12", evaluations: 1104, highRisk: 51 },
  { date: "09-13", evaluations: 878, highRisk: 38 },
  { date: "09-14", evaluations: 642, highRisk: 24 },
  { date: "09-15", evaluations: 735, highRisk: 30 },
  { date: "09-16", evaluations: 1289, highRisk: 63 },
  { date: "09-17", evaluations: 1362, highRisk: 58 },
  { date: "09-18", evaluations: 1244, highRisk: 47 },
  { date: "09-19", evaluations: 1158, highRisk: 44 },
  { date: "09-20", evaluations: 906, highRisk: 33 },
  { date: "09-21", evaluations: 812, highRisk: 29 },
  { date: "09-22", evaluations: 1338, highRisk: 66 },
  { date: "09-23", evaluations: 1394, highRisk: 71 },
  { date: "09-24", evaluations: 1462, highRisk: 74 },
];

export const riskDistribution: RiskDistributionItem[] = [
  { level: "low", label: "低风险", value: 8420 },
  { level: "medium", label: "中风险", value: 4058 },
  { level: "high", label: "高风险", value: 386 },
];

export const systemServices: SystemService[] = [
  {
    name: "评分模型服务",
    desc: "XGBoost v4.2 在线推理",
    status: "operational",
    latency: "86 ms",
    uptime: "99.98%",
  },
  {
    name: "知识图谱查询",
    desc: "2–3 跳关系检索与传导计算",
    status: "operational",
    latency: "142 ms",
    uptime: "99.91%",
  },
  {
    name: "海外征信数据源",
    desc: "12 个国别数据源同步",
    status: "degraded",
    latency: "612 ms",
    uptime: "97.40%",
  },
  {
    name: "报告生成引擎",
    desc: "流式正文 + 引用装配",
    status: "operational",
    latency: "1.2 s",
    uptime: "99.95%",
  },
];

export const presetCases: PresetCase[] = [
  {
    id: "PC-01",
    companyId: "C-1001",
    title: "稳健型 · 精密制造核心供应商",
    summary: "低风险，建议给予大额长期授信并延长账期。",
    riskLevel: "low",
  },
  {
    id: "PC-02",
    companyId: "C-1005",
    title: "关注型 · 实控人变更 + 关联担保",
    summary: "中风险，建议缩短账期、增加抵押与担保条款。",
    riskLevel: "medium",
  },
  {
    id: "PC-03",
    companyId: "C-1008",
    title: "预警型 · 多起诉讼与逾期",
    summary: "高风险，建议拒贷或仅提供信用证结算方式。",
    riskLevel: "high",
  },
];

export const modelMetrics: ModelMetric[] = [
  { key: "auc", label: "AUC", value: "0.874", hint: "较上版 +0.016" },
  { key: "ks", label: "KS", value: "0.412", hint: "较上版 +0.021" },
  { key: "lift", label: "Lift@10%", value: "3.28", hint: "较上版 +0.14" },
  { key: "brier", label: "Brier", value: "0.086", hint: "较上版 -0.007" },
];