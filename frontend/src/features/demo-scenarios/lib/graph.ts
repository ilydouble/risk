import { chartPalette } from "@/shared/config/theme/palette";
import type {
  Company,
  CompanyProfile,
  GraphData,
  GraphEdge,
  GraphEdgeType,
  GraphNode,
  GraphNodeType,
  RelatedParty,
  RiskLevel,
  RiskPath,
} from "@/entities/demo/model/types";

export type Lang = "zh" | "en";

const L = (lang: Lang, zh: string, en: string): string =>
  lang === "en" ? en : zh;

export const nodeTypeMeta: Record<
  GraphNodeType,
  { label: string; labelEn: string; icon: string; short: string; shortEn: string }
> = {
  company: {
    label: "评估主体",
    labelEn: "Assessed entity",
    icon: "ri-building-2-line",
    short: "主体",
    shortEn: "Self",
  },
  owner: {
    label: "控股 / 实控",
    labelEn: "Controller",
    icon: "ri-user-star-line",
    short: "控股",
    shortEn: "Ctrl",
  },
  subsidiary: {
    label: "子公司",
    labelEn: "Subsidiary",
    icon: "ri-git-branch-line",
    short: "子",
    shortEn: "Sub",
  },
  supplier: {
    label: "供应商",
    labelEn: "Supplier",
    icon: "ri-truck-line",
    short: "供",
    shortEn: "Sup",
  },
  guarantor: {
    label: "被担保方",
    labelEn: "Guaranteed party",
    icon: "ri-shield-cross-line",
    short: "担",
    shortEn: "Gua",
  },
  client: {
    label: "客户 / 业主",
    labelEn: "Client / owner",
    icon: "ri-shopping-bag-3-line",
    short: "客",
    shortEn: "Cli",
  },
  counterparty: {
    label: "对手方",
    labelEn: "Counterparty",
    icon: "ri-scales-3-line",
    short: "对",
    shortEn: "Ctr",
  },
  person: {
    label: "自然人",
    labelEn: "Individual",
    icon: "ri-user-line",
    short: "人",
    shortEn: "Per",
  },
  bank: {
    label: "金融机构",
    labelEn: "Financial institution",
    icon: "ri-bank-line",
    short: "金",
    shortEn: "Fin",
  },
  fund: {
    label: "投资基金",
    labelEn: "Investment fund",
    icon: "ri-funds-box-line",
    short: "基",
    shortEn: "Fnd",
  },
};

export const riskColor: Record<RiskLevel, string> = {
  low: chartPalette.riskLow,
  medium: chartPalette.riskMedium,
  high: chartPalette.riskHigh,
};

export const riskLabel: Record<RiskLevel, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
};

export const riskLabelEn: Record<RiskLevel, string> = {
  low: "Low risk",
  medium: "Medium risk",
  high: "High risk",
};

export const edgeTypeMeta: Record<
  GraphEdgeType,
  { label: string; labelEn: string; color: string; dashed: boolean }
> = {
  equity: {
    label: "持股",
    labelEn: "Equity",
    color: "#8a90a0",
    dashed: false,
  },
  control: {
    label: "控制",
    labelEn: "Control",
    color: "#a9aebd",
    dashed: false,
  },
  guarantee: {
    label: "担保",
    labelEn: "Guarantee",
    color: "#b6770b",
    dashed: true,
  },
  supply: {
    label: "供应",
    labelEn: "Supply",
    color: "#969ba9",
    dashed: true,
  },
  trade: {
    label: "交易往来",
    labelEn: "Trade",
    color: "#8a90a0",
    dashed: false,
  },
  loan: {
    label: "授信 / 结算",
    labelEn: "Credit / settlement",
    color: "#a2a7b3",
    dashed: false,
  },
};

const CHILD_POOL: Record<GraphNodeType, { zh: string[]; en: string[] }> = {
  company: {
    zh: ["区域经营主体"],
    en: ["Regional operating entity"],
  },
  owner: {
    zh: ["母集团控股平台", "家族信托（上层）", "产业投资控股"],
    en: ["Group holding platform", "Family trust (upper)", "Industrial holdings"],
  },
  subsidiary: {
    zh: ["员工持股平台", "少数股东持股平台", "地方国资平台"],
    en: ["ESOP platform", "Minority shareholder platform", "Local SOE platform"],
  },
  supplier: {
    zh: ["上游二级材料供应商", "二级零部件供应商", "基础原料供应商"],
    en: ["Tier-2 material supplier", "Tier-2 component supplier", "Base material supplier"],
  },
  guarantor: {
    zh: ["被担保方实际经营主体", "互保关联制造企业", "关联贸易主体"],
    en: ["Guaranteed operator", "Mutual-guarantee manufacturer", "Affiliate trading entity"],
  },
  client: {
    zh: ["终端分销渠道", "区域总代理", "海外经销平台"],
    en: ["End distribution channel", "Regional distributor", "Overseas sales platform"],
  },
  counterparty: {
    zh: ["仲裁相对方", "关联应收方", "诉讼对方"],
    en: ["Arbitration counterparty", "Affiliate receivable", "Litigation opponent"],
  },
  person: {
    zh: ["一致行动人", "管理层亲属", "关联自然人"],
    en: ["Concert party", "Management relative", "Related individual"],
  },
  bank: {
    zh: ["银团成员行", "政策性银行", "同业授信行"],
    en: ["Syndicate member bank", "Policy bank", "Interbank lender"],
  },
  fund: {
    zh: ["二期产业基金", "战略投资联合体", "并购基金 LP"],
    en: ["Fund II", "Strategic investment vehicle", "M&A fund LP"],
  },
};

const CHILD_RELATION: Record<GraphNodeType, { zh: string; en: string }> = {
  company: { zh: "关联主体", en: "related entity" },
  owner: { zh: "上层持股平台", en: "upper holding platform" },
  subsidiary: { zh: "少数股东", en: "minority shareholder" },
  supplier: { zh: "二级供应商", en: "Tier-2 supplier" },
  guarantor: { zh: "被担保主体", en: "guaranteed entity" },
  client: { zh: "下游渠道", en: "downstream channel" },
  counterparty: { zh: "关联对手方", en: "related counterparty" },
  person: { zh: "关联自然人", en: "related individual" },
  bank: { zh: "银团成员", en: "syndicate member" },
  fund: { zh: "合伙投资人", en: "fund investor" },
};

const CHILD_EDGE: Record<GraphNodeType, GraphEdgeType> = {
  company: "trade",
  owner: "equity",
  subsidiary: "equity",
  supplier: "supply",
  guarantor: "guarantee",
  client: "trade",
  counterparty: "trade",
  person: "control",
  bank: "loan",
  fund: "equity",
};

function hash(input: string): number {
  let value = 0;
  for (let i = 0; i < input.length; i += 1) {
    value = (value * 31 + input.charCodeAt(i)) >>> 0;
  }
  return value;
}

function pick<T>(list: T[], seed: number): T {
  return list[seed % list.length];
}

function detectNodeType(party: RelatedParty): GraphNodeType {
  const relation = `${party.relation} ${party.relationEn ?? ""}`;
  if (/实际控制人|控股股东|一致行动|actual controller|concert/i.test(relation))
    return "person";
  if (/战略投资人|合资方|投资基金|investor|fund/i.test(relation)) return "fund";
  if (/子公司|subsidiary/i.test(relation)) return "subsidiary";
  if (/供应商|supplier/i.test(relation)) return "supplier";
  if (/被担保方|担保|guarant/i.test(relation)) return "guarantor";
  if (/业主|客户|集采|client|owner/i.test(relation)) return "client";
  if (/原告|仲裁|对手方|债权|counterparty|litigat/i.test(relation))
    return "counterparty";
  if (/关联方|affiliate/i.test(relation)) return "counterparty";
  return "counterparty";
}

function edgeTypeForParty(party: RelatedParty, type: GraphNodeType): GraphEdgeType {
  const raw = party.exposure;
  if (type === "guarantor") return "guarantee";
  if (/担保/.test(raw)) return "guarantee";
  if (/持股|股权/.test(raw)) return "equity";
  if (/采购/.test(raw)) return "supply";
  if (/订单|往来|应收|涉诉/.test(raw)) return "trade";
  return CHILD_EDGE[type];
}

function edgeLabelForParty(
  party: RelatedParty,
  type: GraphNodeType,
  lang: Lang,
): string {
  const raw = party.exposure;
  if (type === "guarantor") return L(lang, "连带担保", "Joint guarantee");
  if (/持股|股权/.test(raw)) return L(lang, "持股关系", "Equity stake");
  if (/采购/.test(raw)) return L(lang, "采购关系", "Purchase relation");
  if (/订单/.test(raw)) return L(lang, "订单关系", "Order relation");
  if (/涉诉/.test(raw)) return L(lang, "涉诉关联", "Litigation relation");
  if (/赠与|往来/.test(raw)) return L(lang, "资金往来", "Fund transfer");
  return L(lang, nodeTypeMeta[type].label, nodeTypeMeta[type].labelEn);
}

function matchCompanyId(name: string, companies: Company[]): string | undefined {
  const target = name.trim();
  if (!target) return undefined;
  const hit = companies.find(
    (company) => company.nameCn === target || company.nameEn === target,
  );
  return hit?.id;
}

interface BuildContext {
  companies: Company[];
  root: Company;
  lang: Lang;
}

function makeNode(
  id: string,
  label: string,
  type: GraphNodeType,
  riskLevel: RiskLevel,
  hop: number,
  relation: string,
  exposure: string,
  ctx: BuildContext,
  note: string,
): GraphNode {
  return {
    id,
    label,
    type,
    riskLevel,
    hop,
    relation,
    exposure,
    industry: ctx.lang === "en" ? (ctx.root.industryEn ?? ctx.root.industry) : ctx.root.industry,
    country: ctx.lang === "en" ? (ctx.root.countryEn ?? ctx.root.country) : ctx.root.country,
    companyId: matchCompanyId(label, ctx.companies),
    note,
  };
}

function childRisk(parent: RiskLevel, seed: number): RiskLevel {
  if (parent === "high") return "high";
  if (parent === "medium") return seed % 3 === 0 ? "high" : "medium";
  return seed % 5 === 0 ? "medium" : "low";
}

function childExposure(type: GraphNodeType, seed: number, lang: Lang): string {
  const a = (seed % 32) + 5;
  const b = seed % 10;
  switch (type) {
    case "owner":
    case "fund":
    case "subsidiary":
      return L(lang, `持股 ${a}.${b}%`, `Stake ${a}.${b}%`);
    case "guarantor":
      return L(lang, `担保 ${a},${b}00 万元`, `Guarantee ¥${a},${b}00k`);
    case "supplier":
      return L(lang, `年采购 ${a},${b}00 万元`, `Annual purchase ¥${a},${b}00k`);
    case "client":
      return L(lang, `年订单 ${a},${b}00 万元`, `Annual orders ¥${a},${b}00k`);
    case "bank":
      return L(lang, `授信 ${a},${b}00 万元`, `Credit line ¥${a},${b}00k`);
    default:
      return L(lang, `往来 ${a},${b}00 万元`, `Turnover ¥${a},${b}00k`);
  }
}

function buildChild(
  parent: GraphNode,
  index: number,
  hop: number,
  ctx: BuildContext,
): GraphNode {
  const { lang } = ctx;
  const seed = hash(`${parent.id}-${hop}-${index}`);
  const type = parent.type === "person" ? "person" : parent.type;
  const pool = CHILD_POOL[type];
  const relation = CHILD_RELATION[type];
  const label = pick(lang === "en" ? pool.en : pool.zh, seed);
  const risk = childRisk(parent.riskLevel, seed);
  const relText = L(lang, relation.zh, relation.en);
  const riskText = L(lang, riskLabel[risk], riskLabelEn[risk]);
  const note =
    lang === "en"
      ? `Through equity and transaction look-through, a "${relText}" relation to "${parent.label}" was identified, judged ${riskText}.`
      : `经股权与交易穿透，识别到「${parent.label}」的${relText}关系，风险等级判定为${riskText}。`;
  return makeNode(
    `${parent.id}-h${hop}-${index}`,
    label,
    type,
    risk,
    hop,
    relText,
    childExposure(type, seed, lang),
    ctx,
    note,
  );
}

function makeEdge(
  source: string,
  target: string,
  type: GraphEdgeType,
  label: string,
  strength = 1,
): GraphEdge {
  return {
    id: `E:${source}->${target}`,
    source,
    target,
    type,
    label,
    riskFlow: false,
    strength,
  };
}

/**
 * Builds a 3-hop relation graph for a company from its profile.
 * Deterministic — same company (+ language) always yields the same network.
 */
export function buildGraphData(
  companies: Company[],
  company: Company,
  profile: CompanyProfile,
  lang: Lang = "zh",
): GraphData {
  const ctx: BuildContext = { companies, root: company, lang };
  const rootId = company.id;
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];

  const name = lang === "en" ? company.nameEn : company.nameCn;

  nodes.push({
    id: rootId,
    label: name,
    type: "company",
    riskLevel: company.riskLevel,
    hop: 0,
    relation: L(lang, "评估主体", "Assessed entity"),
    exposure: L(lang, `建议授信 ${company.creditLimit}`, `Suggested limit ${company.creditLimit}`),
    industry: lang === "en" ? (company.industryEn ?? company.industry) : company.industry,
    country: lang === "en" ? (company.countryEn ?? company.country) : company.country,
    companyId: company.id,
    note: lang === "en" ? (profile.summaryEn ?? profile.summary) : profile.summary,
  });

  const hop1: GraphNode[] = [];

  profile.relatedParties.forEach((party) => {
    const type = detectNodeType(party);
    const partyName = lang === "en" ? (party.nameEn ?? party.name) : party.name;
    const relation = lang === "en" ? (party.relationEn ?? party.relation) : party.relation;
    const exposure = lang === "en" ? (party.exposureEn ?? party.exposure) : party.exposure;
    const riskText = L(lang, riskLabel[party.riskLevel], riskLabelEn[party.riskLevel]);
    const note =
      lang === "en"
        ? `Constitutes a "${relation}" relation with the assessed entity, exposure ${exposure}, judged ${riskText}.`
        : `与评估主体构成「${relation}」关系，敞口为 ${exposure}，风险等级为${riskText}。`;
    const node = makeNode(
      party.id,
      partyName,
      type,
      party.riskLevel,
      1,
      relation,
      exposure,
      ctx,
      note,
    );
    nodes.push(node);
    hop1.push(node);
    edges.push(
      makeEdge(
        rootId,
        node.id,
        edgeTypeForParty(party, type),
        edgeLabelForParty(party, type, lang),
        1.4,
      ),
    );
  });

  const existingLabels = new Set(hop1.map((node) => node.label));
  const factsEn = profile.factsEn;

  // Legal representative (skip if already covered by a related party).
  const legalPerson =
    lang === "en"
      ? (factsEn?.legalPerson ?? profile.facts.legalPerson)
      : profile.facts.legalPerson;
  if (!existingLabels.has(profile.facts.legalPerson)) {
    const stake =
      lang === "en"
        ? (factsEn?.controllerStake ?? profile.facts.controllerStake)
        : profile.facts.controllerStake;
    const personNode = makeNode(
      `N-${rootId}-legal`,
      legalPerson,
      "person",
      company.riskLevel === "high" ? "medium" : "low",
      1,
      L(lang, "法定代表人", "Legal representative"),
      L(lang, `控制权 ${stake}`, `Control ${stake}`),
      ctx,
      lang === "en"
        ? `Registered legal representative and a core member of the controlling party, control stake ${stake}.`
        : `工商登记法定代表人，同时为实际控制方核心成员，控制权比例 ${stake}。`,
    );
    nodes.push(personNode);
    hop1.push(personNode);
    edges.push(
      makeEdge(rootId, personNode.id, "control", L(lang, "控制关系", "Control"), 1.2),
    );
  }

  // Main relationship bank.
  const bankRaw =
    lang === "en"
      ? (factsEn?.mainBanks ?? profile.facts.mainBanks)
      : profile.facts.mainBanks;
  const bankName = bankRaw.split("·")[0].trim();
  if (bankName) {
    const settlement =
      lang === "en"
        ? (factsEn?.settlement ?? profile.facts.settlement)
        : profile.facts.settlement;
    const bankNode = makeNode(
      `N-${rootId}-bank`,
      bankName,
      "bank",
      "low",
      1,
      L(lang, "主要往来银行", "Main bank"),
      settlement,
      ctx,
      lang === "en"
        ? `Primary settlement and credit bank, settlement terms "${settlement}"; channel concentration needs ongoing attention.`
        : `主要结算与授信银行，结算方式为「${settlement}」，渠道集中度需持续关注。`,
    );
    nodes.push(bankNode);
    hop1.push(bankNode);
    edges.push(makeEdge(rootId, bankNode.id, "loan", L(lang, "授信 / 结算", "Credit / settlement")));
  }

  // Key downstream client.
  const clientNode = makeNode(
    `N-${rootId}-client`,
    L(lang, `${company.sector}核心下游客户`, `Key downstream client · ${company.sector}`),
    "client",
    company.riskLevel === "high" ? "high" : "medium",
    1,
    L(lang, "主要客户", "Key client"),
    L(lang, "年订单占比 18.6%", "18.6% of annual orders"),
    ctx,
    lang === "en"
      ? "Core downstream demand source of the assessed entity, 18.6% of revenue; its payment capacity directly affects the collection cycle."
      : `评估主体的核心下游需求方，收入占比 18.6%，其付款能力直接影响回款周期。`,
  );
  nodes.push(clientNode);
  hop1.push(clientNode);
  edges.push(makeEdge(rootId, clientNode.id, "trade", L(lang, "交易往来", "Trade")));

  // Hop 2 — one child per hop-1 node.
  const hop2: GraphNode[] = [];
  hop1.forEach((parent, index) => {
    const child = buildChild(parent, index, 2, ctx);
    nodes.push(child);
    hop2.push(child);
    edges.push(
      makeEdge(
        parent.id,
        child.id,
        CHILD_EDGE[child.type],
        L(lang, edgeTypeMeta[CHILD_EDGE[child.type]].label, edgeTypeMeta[CHILD_EDGE[child.type]].labelEn),
      ),
    );
  });

  // Hop 3 — expand the riskiest hop-2 nodes only.
  const riskyHop2 = [...hop2].sort((a, b) => {
    const weight: Record<RiskLevel, number> = { high: 0, medium: 1, low: 2 };
    return weight[a.riskLevel] - weight[b.riskLevel];
  });
  riskyHop2.slice(0, 2).forEach((parent, index) => {
    const child = buildChild(parent, index + 10, 3, ctx);
    nodes.push(child);
    edges.push(
      makeEdge(
        parent.id,
        child.id,
        CHILD_EDGE[child.type],
        L(lang, edgeTypeMeta[CHILD_EDGE[child.type]].label, edgeTypeMeta[CHILD_EDGE[child.type]].labelEn),
      ),
    );
  });

  const graph: GraphData = { rootId, nodes, edges };
  applyRiskTransmission(graph);
  return graph;
}

function buildAdjacency(edges: GraphEdge[]) {
  const adjacency = new Map<string, { to: string; edgeId: string }[]>();
  edges.forEach((edge) => {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, []);
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, []);
    adjacency.get(edge.source)!.push({ to: edge.target, edgeId: edge.id });
    adjacency.get(edge.target)!.push({ to: edge.source, edgeId: edge.id });
  });
  return adjacency;
}

function shortestPaths(
  rootId: string,
  adjacency: Map<string, { to: string; edgeId: string }[]>,
) {
  const parentEdge = new Map<string, string>();
  const parentNode = new Map<string, string>();
  const visited = new Set<string>([rootId]);
  const queue: string[] = [rootId];

  while (queue.length) {
    const current = queue.shift()!;
    (adjacency.get(current) ?? []).forEach((link) => {
      if (visited.has(link.to)) return;
      visited.add(link.to);
      parentEdge.set(link.to, link.edgeId);
      parentNode.set(link.to, current);
      queue.push(link.to);
    });
  }

  const chainFor = (nodeId: string): string[] => {
    const chain: string[] = [nodeId];
    let cursor = nodeId;
    let guard = 0;
    while (parentNode.has(cursor) && guard < 40) {
      cursor = parentNode.get(cursor)!;
      chain.unshift(cursor);
      guard += 1;
    }
    return chain;
  };

  return { parentEdge, chainFor };
}

/** Marks every edge that sits on a path from the root to a high-risk node. */
export function applyRiskTransmission(graph: GraphData): RiskPath[] {
  const { rootId, nodes, edges } = graph;
  const adjacency = buildAdjacency(edges);
  const { parentEdge, chainFor } = shortestPaths(rootId, adjacency);

  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const highNodes = nodes.filter(
    (node) => node.id !== rootId && node.riskLevel === "high",
  );
  const targets = highNodes.length
    ? highNodes
    : nodes.filter((node) => node.id !== rootId && node.riskLevel === "medium");

  const flowEdges = new Set<string>();
  const paths: RiskPath[] = targets.map((node) => {
    const chain = chainFor(node.id);
    for (let i = 0; i < chain.length - 1; i += 1) {
      flowEdges.add(parentEdge.get(chain[i + 1]) ?? "");
    }
    return {
      nodeId: node.id,
      label: node.label,
      riskLevel: node.riskLevel,
      hops: chain.length - 1,
      chain: chain.map((id) => nodeMap.get(id)?.label ?? id),
    };
  });

  edges.forEach((edge) => {
    edge.riskFlow = flowEdges.has(edge.id);
  });

  return paths.sort((a, b) => b.hops - a.hops);
}