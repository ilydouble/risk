export default {
  graph: {
    title: "Graph Relations",
    subtitle:
      "A 1–3 hop relation network with risk-colored nodes and highlighted transmission paths",
    snapshot:
      "Graph snapshot · Sources: registry / judicial / supply-chain · Updated {{date}}",
    stats: {
      related: "Related parties mapped",
      highRisk: "High-risk related parties",
      paths: "Risk transmission paths",
      edges: "Relation edges",
      relatedUnit: "",
      highRiskUnit: "",
      pathsUnit: "",
      edgesUnit: "",
    },
    network: {
      title: "Relation network",
      subtitle: "{{depth}}-hop look-through · {{count}} nodes",
      badge: "Force layout · Live solve",
    },
    legend: {
      risk: "Risk coloring",
      edge: "Relation types",
      riskPath: "Risk transmission path",
    },
    toolbar: {
      subject: "Assessed entity",
      depth: "Look-through depth",
      depthValue: "{{count}} hop",
      focus: "Risk transmission only",
    },
    inspector: {
      title: "Node details",
      emptySubtitle: "Click any node in the graph to inspect it",
      empty:
        "No node selected. Drag nodes to adjust the layout, or click a node to view relations, exposure and risk origin.",
      subtitle: "Relations, exposure and risk origin",
      nodeType: "Node type",
      relation: "Relation",
      exposure: "Exposure / scale",
      country: "Country",
      industry: "Industry",
      hop: "Look-through hop",
      root: "Assessed entity",
      hopValue: "{{count}} hop",
      direct: "Direct relations ({{count}})",
      riskFlow: "Risk transmission",
      viewProfile: "View profile",
      focusCenter: "Center on this entity",
      drill: "Drill down",
    },
    path: {
      title: "Risk transmission paths",
      subtitle: "High-risk chains leading to the assessed entity",
      focus: "Focus paths",
      focused: "Focused",
      empty:
        "No high-risk transmission chain detected; related-party risk stays within a manageable range.",
      hops: "{{count}} hop",
      locate: "Locate entity",
      tip: "{{count}} high-risk transmission chains detected. Focus on guarantee chains and related-party transactions in underwriting, and set cross-default and additional guarantee clauses on downstream entities.",
    },
    info: {
      title: "How to read the graph",
      subtitle: "Interpretation of the relations",
      centerTitle: "Centered on the assessed entity",
      centerDesc:
        "The root node is the target company, expanding 1–3 hops across equity, guarantee, trade and credit relations.",
      pathTitle: "Red dashed lines are risk transmission paths",
      pathDesc:
        "The shortest chain from a high-risk party back to the assessed entity, indicating a possible origin of risk.",
      drillTitle: "Click a node to drill down",
      drillDesc:
        "Once selected, view exposure and direct relations, and re-expand the network centered on it.",
      footer: "Current entity risk level is {{risk}}, model version v4.2.",
    },
  },
};
