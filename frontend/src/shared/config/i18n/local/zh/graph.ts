export default {
  graph: {
    title: "图谱关系",
    subtitle:
      "以关系图谱呈现企业 1–3 跳关联网络，节点按风险染色并高亮风险传导路径",
    snapshot:
      "图谱快照 · 数据来源：工商登记 / 司法信息 / 供应链数据 · 最近更新 {{date}}",
    stats: {
      related: "已穿透关联主体",
      highRisk: "高风险关联方",
      paths: "风险传导链路",
      edges: "关系边数量",
      relatedUnit: "个",
      highRiskUnit: "个",
      pathsUnit: "条",
      edgesUnit: "条",
    },
    network: {
      title: "关系网络",
      subtitle: "按 {{depth}} 跳穿透 · 共 {{count}} 个节点",
      badge: "力导向布局 · 实时求解",
    },
    legend: {
      risk: "风险染色",
      edge: "关系类型",
      riskPath: "风险传导路径",
    },
    toolbar: {
      subject: "评估主体",
      depth: "穿透层级",
      depthValue: "{{count}} 跳",
      focus: "只看风险传导路径",
    },
    inspector: {
      title: "节点详情",
      emptySubtitle: "点击图谱中的任意节点查看穿透信息",
      empty:
        "尚未选中节点。可拖拽节点调整布局，或点击节点查看关系、敞口与风险来源。",
      subtitle: "关联关系、敞口与风险来源",
      nodeType: "节点类型",
      relation: "关联关系",
      exposure: "敞口 / 规模",
      country: "国别",
      industry: "行业",
      hop: "穿透层级",
      root: "评估主体",
      hopValue: "{{count}} 跳",
      direct: "直接关联（{{count}}）",
      riskFlow: "风险传导",
      viewProfile: "查看企业画像",
      focusCenter: "以该主体为中心",
      drill: "下钻展开",
    },
    path: {
      title: "风险传导路径",
      subtitle: "从评估主体出发的高风险传导链路",
      focus: "聚焦路径",
      focused: "已聚焦",
      empty: "当前网络未检出高风险传导链路，关联方风险处于可控区间。",
      hops: "{{count}} 跳",
      locate: "定位该主体",
      tip: "共检出 {{count}} 条高风险传导链路。建议在授信中重点关注担保链与关联交易，对传导路径末端主体设置交叉违约与追加担保条款。",
    },
    info: {
      title: "图谱说明",
      subtitle: "关联关系的解读口径",
      centerTitle: "以评估主体为中心",
      centerDesc:
        "根节点为待评估企业，按 1–3 跳穿透股权、担保、交易与授信关系。",
      pathTitle: "红色虚线为风险传导路径",
      pathDesc:
        "自高风险主体回溯至评估主体的最短链路，提示风险可能的传导来源。",
      drillTitle: "点击节点可下钻",
      drillDesc:
        "选中节点后可查看敞口与直接关联，并支持以其为中心重新展开网络。",
      footer: "当前主体风险等级为{{risk}}，模型版本 v4.2。",
    },
  },
};
