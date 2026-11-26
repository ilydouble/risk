const names: Record<string, string> = {
  "riskgnn-plus": "RiskGNN+",
  gcn: "GCN",
  rgcn: "RGCN",
  hgt: "HGT",
  gbdt: "GBDT",
  "g2s-gbdt": "Graph-to-State + GBDT",
  lr: "Logistic Regression",
  mlp: "MLP",
};

export function algorithmName(algorithm: string) {
  return names[algorithm] ?? algorithm;
}
