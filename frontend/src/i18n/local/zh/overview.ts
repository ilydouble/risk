export default {
  overview: {
    title: "总览看板",
    subtitle: "全球企业信用覆盖、风险评估实时监控与系统运行状态",
    actions: {
      batch: "批量评估",
      newEval: "发起新评估",
      viewAll: "查看全部",
      modelCard: "模型档案",
    },
    ranges: {
      d7: "近 7 天",
      d14: "近 14 天",
    },
    stats: {
      covered: "覆盖企业数",
      coveredDelta: "+3.2% 环比",
      today: "今日评估量",
      todayDelta: "+128 较昨日",
      highRisk: "高风险企业",
      highRiskDelta: "+12 近 7 天",
      avgScore: "平均信用分",
      avgScoreUnit: "/ 1000",
      avgDelta: "-4 较上季",
    },
    chart: {
      trendTitle: "评估量与高风险趋势",
      trendSubtitle: "按日统计的评估请求与高风险识别数量",
      seriesEvaluations: "评估量",
      seriesHighRisk: "高风险量",
    },
    risk: {
      title: "风险分布",
      subtitle: "按风险等级划分的覆盖企业占比",
      centerLabel: "覆盖企业数",
      low: "低风险",
      medium: "中风险",
      high: "高风险",
    },
    system: {
      title: "系统状态",
      subtitle: "核心服务健康度与响应时延",
    },
    recent: {
      title: "最近评估企业",
      subtitle: "最新完成的授信评估记录",
      colCompany: "企业",
      colScore: "信用分",
      colPd: "违约概率",
      colRisk: "风险等级",
      colAction: "操作",
      viewScore: "评分详情",
    },
    model: {
      title: "模型核心指标",
      subtitle: "v4.2 版本离线验证结果",
      metrics: {
        auc: "较上版 +0.016",
        ks: "较上版 +0.021",
        lift: "较上版 +0.14",
        brier: "较上版 -0.007",
      },
    },
    demo: {
      active: "演示模式已开启",
      desc: "已加载脱敏演示数据与 3 个预置案例，可直接体验完整授信评估链路。",
    },
    services: {
      scoring: { name: "评分模型服务", desc: "XGBoost v4.2 在线推理" },
      graph: { name: "知识图谱查询", desc: "2–3 跳关系检索与传导计算" },
      credit: { name: "海外征信数据源", desc: "12 个国别数据源同步" },
      report: { name: "报告生成引擎", desc: "流式正文 + 引用装配" },
    },
    preset: {
      PC01: {
        title: "稳健型 · 精密制造核心供应商",
        summary: "低风险，建议给予大额长期授信并延长账期。",
      },
      PC02: {
        title: "关注型 · 实控人变更 + 关联担保",
        summary: "中风险，建议缩短账期、增加抵押与担保条款。",
      },
      PC03: {
        title: "预警型 · 多起诉讼与逾期",
        summary: "高风险，建议拒贷或仅提供信用证结算方式。",
      },
    },
  },
};