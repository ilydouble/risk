import { riskLabel, riskLabelEn } from "@/pages/graph/lib/graph";
import type {
  Company,
  CompanyProfile,
  CreditLimitBand,
  DecisionDoc,
  DecisionOutcome,
  DecisionRule,
  DecisionRuleSeverity,
  DecisionTerm,
  LimitFactor,
  MitigationMeasure,
  RiskLevel,
  ScoreDetail,
} from "@/types";

export type Lang = "zh" | "en";

const L = (lang: Lang, zh: string, en: string): string =>
  lang === "en" ? en : zh;

export const decisionOutcomeMeta: Record<
  DecisionOutcome,
  { label: string; labelEn: string; icon: string; note: string; noteEn: string }
> = {
  approve: {
    label: "建议通过",
    labelEn: "Recommended · approve",
    icon: "ri-checkbox-circle-line",
    note: "主体资质与风险表现符合授信标准，按建议额度与标准条件办理。",
    noteEn:
      "The entity's profile and risk performance meet the underwriting standard; proceed on the suggested limit and standard terms.",
  },
  conditional: {
    label: "有条件通过",
    labelEn: "Conditional approval",
    icon: "ri-error-warning-line",
    note: "存在需关注事项，须落实增信与账期约束后方可放款。",
    noteEn:
      "There are watch items; disburse only after credit enhancement and tenor constraints are implemented.",
  },
  reject: {
    label: "建议不新增授信",
    labelEn: "No new credit recommended",
    icon: "ri-forbid-2-line",
    note: "风险信号集中，建议暂停新增信用敞口，仅保留风险可控的结算方式。",
    noteEn:
      "Concentrated risk signals; suspend new credit exposure and keep only risk-controlled settlement methods.",
  },
};

export const ruleSeverityMeta: Record<
  DecisionRuleSeverity,
  { label: string; labelEn: string; icon: string; className: string }
> = {
  pass: {
    label: "通过",
    labelEn: "Pass",
    icon: "ri-checkbox-circle-line",
    className: "border-primary-400/40 bg-primary-500/10 text-primary-400",
  },
  warn: {
    label: "提示",
    labelEn: "Warning",
    icon: "ri-alert-line",
    className: "border-accent-500/40 bg-accent-500/10 text-accent-400",
  },
  block: {
    label: "拦截",
    labelEn: "Block",
    icon: "ri-close-circle-line",
    className: "risk-border-high risk-soft-high risk-text-high",
  },
};

const CURRENCY_MAP: Record<string, { zh: string; en: string }> = {
  "¥": { zh: "人民币 CNY", en: "Chinese yuan CNY" },
  "€": { zh: "欧元 EUR", en: "Euro EUR" },
  "$": { zh: "美元 USD", en: "US dollar USD" },
  "HK$": { zh: "港币 HKD", en: "Hong Kong dollar HKD" },
  "S$": { zh: "新加坡元 SGD", en: "Singapore dollar SGD" },
  "A$": { zh: "澳元 AUD", en: "Australian dollar AUD" },
  "R$": { zh: "巴西雷亚尔 BRL", en: "Brazilian real BRL" },
  "₽": { zh: "俄罗斯卢布 RUB", en: "Russian ruble RUB" },
  "₫": { zh: "越南盾 VND", en: "Vietnamese dong VND" },
};

const WATCH_COUNTRIES = ["俄罗斯", "土耳其", "尼日利亚", "埃及", "Russia", "Turkey", "Nigeria", "Egypt"];

const APPROVERS = [
  { zh: "陈立恒 · 授信审批部", en: "Chen Liheng · Credit Approval" },
  { zh: "赵敏 · 风险管理部", en: "Zhao Min · Risk Management" },
  { zh: "林思远 · 信贷审批中心", en: "Lin Siyuan · Credit Review Center" },
];

interface TermSpec {
  tenor: string;
  tenorEn: string;
  tenorNote: string;
  tenorNoteEn: string;
  settlement: string;
  settlementEn: string;
  settlementNote: string;
  settlementNoteEn: string;
  deposit: string;
  depositEn: string;
  depositNote: string;
  depositNoteEn: string;
  validity: string;
  validityEn: string;
  validityNote: string;
  validityNoteEn: string;
  monitoring: string;
  monitoringEn: string;
  monitoringNote: string;
  monitoringNoteEn: string;
  validityMonths: number;
}

const TERM_SPECS: Record<RiskLevel, TermSpec> = {
  low: {
    tenor: "票到 60 天",
    tenorEn: "60 days from invoice",
    tenorNote: "标准账期，覆盖正常回款周期",
    tenorNoteEn: "Standard tenor covering the normal collection cycle",
    settlement: "银行承兑 / T/T 电汇",
    settlementNote: "优先采用银行承兑降低违约风险",
    settlementEn: "Bank acceptance / T/T wire",
    settlementNoteEn: "Prefer bank acceptance to lower default risk",
    deposit: "0%",
    depositEn: "0%",
    depositNote: "信用方式放款，免收保证金",
    depositNoteEn: "Disbursed on trust, no deposit required",
    validity: "12 个月",
    validityEn: "12 months",
    validityNote: "到期前 30 天启动复审",
    validityNoteEn: "Review starts 30 days before expiry",
    monitoring: "季度贷后监控",
    monitoringEn: "Quarterly post-loan monitoring",
    monitoringNote: "季度财报与工商信息复核",
    monitoringNoteEn: "Quarterly review of financials and registry",
    validityMonths: 12,
  },
  medium: {
    tenor: "货到 45 天",
    tenorEn: "45 days from delivery",
    tenorNote: "压缩账期，降低回款敞口",
    tenorNoteEn: "Compressed tenor to reduce collection exposure",
    settlement: "T/T 电汇 + 部分保证金",
    settlementEn: "T/T wire + partial deposit",
    settlementNote: "配套保证金与应收账款保理",
    settlementNoteEn: "Paired with a deposit and receivables factoring",
    deposit: "10%",
    depositEn: "10%",
    depositNote: "按单笔业务金额收取",
    depositNoteEn: "Charged per transaction amount",
    validity: "6 个月",
    validityEn: "6 months",
    validityNote: "到期前 15 天启动复审",
    validityNoteEn: "Review starts 15 days before expiry",
    monitoring: "月度监控 + 账龄跟踪",
    monitoringEn: "Monthly monitoring + aging tracking",
    monitoringNote: "按月跟踪应收账款账龄结构",
    monitoringNoteEn: "Track receivable aging monthly",
    validityMonths: 6,
  },
  high: {
    tenor: "预付款 30%，发货前结清",
    tenorEn: "30% prepaid, settled before shipment",
    tenorNote: "不形成信用敞口，先款后货",
    tenorNoteEn: "No credit exposure; payment before goods",
    settlement: "即期信用证 / 预付款",
    settlementEn: "Sight LC / prepayment",
    settlementNote: "以银行信用替代商业信用",
    settlementNoteEn: "Replace commercial credit with bank credit",
    deposit: "30% – 100%",
    depositEn: "30% – 100%",
    depositNote: "按订单风险逐笔核定",
    depositNoteEn: "Determined per order by risk",
    validity: "3 个月（单笔审批）",
    validityEn: "3 months (per-transaction approval)",
    validityNote: "每笔业务单独审批后方可执行",
    validityNoteEn: "Executed only after per-transaction approval",
    monitoring: "每周监控 + 单笔审批",
    monitoringEn: "Weekly monitoring + per-transaction approval",
    monitoringNote: "纳入重点关注名单实时监测",
    monitoringNoteEn: "Listed for focused real-time monitoring",
    validityMonths: 3,
  },
};

function hash(input: string): number {
  let value = 0;
  for (let i = 0; i < input.length; i += 1) {
    value = (value * 31 + input.charCodeAt(i)) >>> 0;
  }
  return value;
}

/** Splits a formatted money string into its currency symbol and numeric value. */
export function parseMoney(text: string): { symbol: string; value: number } {
  const match = text.match(/^([^0-9]*)([0-9][0-9,]*)/);
  if (!match) return { symbol: "", value: 0 };
  return {
    symbol: match[1].trim(),
    value: Number(match[2].replace(/,/g, "")) || 0,
  };
}

export function formatMoney(symbol: string, value: number): string {
  return `${symbol} ${Math.round(value).toLocaleString("en-US")}`;
}

function roundAmount(value: number): number {
  const abs = Math.abs(value);
  if (abs >= 1e9) return Math.round(value / 1e6) * 1e6;
  if (abs >= 1e6) return Math.round(value / 1e3) * 1e3;
  if (abs >= 1e3) return Math.round(value / 100) * 100;
  return Math.round(value);
}

function addMonths(dateText: string, months: number): string {
  const [datePart] = dateText.split(" ");
  const [year, month, day] = datePart.split("-").map(Number);
  const base = new Date(Date.UTC(year, month - 1 + months, day));
  const yy = base.getUTCFullYear();
  const mm = String(base.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(base.getUTCDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

interface RuleInput {
  id: string;
  code: string;
  name: string;
  category: DecisionRule["category"];
  categoryEn: string;
  severity: DecisionRuleSeverity;
  condition: string;
  actual: string;
  action: string;
  desc: string;
}

/**
 * Builds a deterministic credit decision order for a company.
 * The recommended limit, terms, mitigations and hit rules are all derived from
 * the same profile / score fields, so the same company (+ language) always
 * yields the same decision and the numbers stay internally consistent.
 */
export function buildDecision(
  company: Company,
  profile: CompanyProfile,
  detail: ScoreDetail,
  lang: Lang = "zh",
): DecisionDoc {
  const { facts } = profile;
  const factsEn = profile.factsEn;
  const isEn = lang === "en";
  const { symbol, value: limitNumeric } = parseMoney(company.creditLimit);
  const risk = company.riskLevel;
  const spec = TERM_SPECS[risk];
  const riskText = L(lang, riskLabel[risk], riskLabelEn[risk]);

  const country = isEn ? (company.countryEn ?? company.country) : company.country;
  const fActualController = isEn ? (factsEn?.actualController ?? facts.actualController) : facts.actualController;
  const fRatingAgency = isEn ? (factsEn?.ratingAgency ?? facts.ratingAgency) : facts.ratingAgency;
  const fPaidInCapital = isEn ? (factsEn?.paidInCapital ?? facts.paidInCapital) : facts.paidInCapital;
  const fRevenue = isEn ? (factsEn?.revenue ?? facts.revenue) : facts.revenue;
  const fNetMargin = isEn ? (factsEn?.netMargin ?? facts.netMargin) : facts.netMargin;

  const highFlags = profile.riskFlags.filter((flag) => flag.level === "high");
  const midFlags = profile.riskFlags.filter((flag) => flag.level === "medium");

  const dim = (key: string) =>
    profile.fiveC.find((item) => item.key === key)?.score ?? 62;
  const character = dim("character");
  const capacity = dim("capacity");
  const capital = dim("capital");
  const collateral = dim("collateral");
  const environment = dim("environment");

  const guarantorCount = profile.relatedParties.filter(
    (party) => /担保/.test(party.relation) || /担保/.test(party.exposure),
  ).length;
  const guaranteeFlagPenalty = profile.riskFlags
    .filter((flag) => /担保/.test(flag.category) || /担保/.test(flag.label))
    .reduce(
      (sum, flag) =>
        sum + (flag.level === "high" ? 3 : flag.level === "medium" ? 2 : 1),
      0,
    );

  const paidMatch = facts.paidInCapital.match(/(\d+)\s*%/);
  const paidRatio = paidMatch ? Number(paidMatch[1]) : 100;

  // --- credit limit: model base + signed risk adjustments -------------------
  const rawFactors = [
    {
      id: "credit",
      label: L(lang, "信用与履约记录", "Credit & performance"),
      detail: L(
        lang,
        `5C 品格维度 ${character}/100 · 外部评级 ${fRatingAgency}`,
        `5C character ${character}/100 · external rating ${fRatingAgency}`,
      ),
      raw: (character - 62) * 0.9,
    },
    {
      id: "capacity",
      label: L(lang, "经营与订单能力", "Operating & order capacity"),
      detail: L(
        lang,
        `5C 能力维度 ${capacity}/100 · ${fRevenue}`,
        `5C capacity ${capacity}/100 · ${fRevenue}`,
      ),
      raw: (capacity - 62) * 0.75,
    },
    {
      id: "capital",
      label: L(lang, "资本结构与杠杆", "Capital structure & leverage"),
      detail: L(
        lang,
        `5C 资本维度 ${capital}/100 · ${fNetMargin}`,
        `5C capital ${capital}/100 · ${fNetMargin}`,
      ),
      raw: (capital - 62) * 0.8,
    },
    {
      id: "guarantee",
      label: L(lang, "关联方担保敞口", "Related-guarantee exposure"),
      detail: L(
        lang,
        `对外担保 / 被担保 ${guarantorCount} 项 · 担保信号压力 ${guaranteeFlagPenalty}`,
        `Guarantee / guaranteed ${guarantorCount} items · signal pressure ${guaranteeFlagPenalty}`,
      ),
      raw: -(guarantorCount * 7 + guaranteeFlagPenalty * 4),
    },
    {
      id: "compliance",
      label: L(lang, "司法与合规表现", "Judicial & compliance"),
      detail: L(
        lang,
        `高风险信号 ${highFlags.length} 项 · 中风险信号 ${midFlags.length} 项`,
        `${highFlags.length} high-risk · ${midFlags.length} medium-risk signals`,
      ),
      raw: -(highFlags.length * 15 + midFlags.length * 5),
    },
    {
      id: "environment",
      label: L(lang, "行业与国别环境", "Industry & country environment"),
      detail: L(
        lang,
        `${country} · ${company.sector} · 5C 环境 ${environment}/100`,
        `${country} · ${company.sector} · 5C environment ${environment}/100`,
      ),
      raw: (environment - 62) * 0.5,
    },
    {
      id: "collateral",
      label: L(lang, "抵押物与增信覆盖", "Collateral & enhancement coverage"),
      detail: L(
        lang,
        `5C 担保维度 ${collateral}/100 · 可增信空间`,
        `5C collateral ${collateral}/100 · enhancement room`,
      ),
      raw: (collateral - 62) * 0.7,
    },
  ];

  const scale = limitNumeric / 420;
  const factors: LimitFactor[] = rawFactors.map((item) => {
    const amount = roundAmount(item.raw * scale);
    return {
      id: item.id,
      label: item.label,
      detail: item.detail,
      amount,
      display: formatMoney(symbol, Math.abs(amount)),
      positive: amount >= 0,
    };
  });

  const adjustSum = factors.reduce((sum, item) => sum + item.amount, 0);
  const baseAmount = limitNumeric - adjustSum;

  const spread: [number, number] =
    risk === "low" ? [0.8, 1.2] : risk === "medium" ? [0.7, 1.15] : [0.6, 1.05];

  const floor = roundAmount(limitNumeric * spread[0]);
  const ceiling = roundAmount(limitNumeric * spread[1]);
  const bands: CreditLimitBand[] = [
    {
      key: "floor",
      label: L(lang, "审慎下限", "Prudent floor"),
      value: floor,
      display: formatMoney(symbol, floor),
      note: L(lang, "压力情形下可压缩至的下限", "Bottom limit under stress"),
      emphasis: false,
    },
    {
      key: "recommend",
      label: L(lang, "建议额度", "Recommended limit"),
      value: limitNumeric,
      display: formatMoney(symbol, limitNumeric),
      note: L(lang, "本次评审建议批准的额度", "Limit recommended for approval"),
      emphasis: true,
    },
    {
      key: "ceiling",
      label: L(lang, "敞口上限", "Exposure ceiling"),
      value: ceiling,
      display: formatMoney(symbol, ceiling),
      note: L(lang, "任何情形下不得突破的上限", "Ceiling that must not be breached"),
      emphasis: false,
    },
  ];

  // --- decision outcome -----------------------------------------------------
  const outcome: DecisionOutcome =
    risk === "low" ? "approve" : risk === "medium" ? "conditional" : "reject";
  const outcomeMeta = decisionOutcomeMeta[outcome];

  const limitLabel =
    outcome === "approve"
      ? L(lang, "建议授信额度", "Suggested credit limit")
      : outcome === "conditional"
        ? L(lang, "附条件授信额度", "Conditional credit limit")
        : L(lang, "单笔风险敞口上限", "Single-transaction exposure cap");

  // --- terms ---------------------------------------------------------------
  const currency = CURRENCY_MAP[symbol]
    ? L(lang, CURRENCY_MAP[symbol].zh, CURRENCY_MAP[symbol].en)
    : L(lang, `${symbol} 计价货币`, `${symbol} currency`);
  const terms: DecisionTerm[] = [
    {
      key: "tenor",
      label: L(lang, "付款账期", "Payment tenor"),
      value: L(lang, spec.tenor, spec.tenorEn),
      note: L(lang, spec.tenorNote, spec.tenorNoteEn),
      icon: "ri-calendar-schedule-line",
      tone: "primary",
    },
    {
      key: "settlement",
      label: L(lang, "结算方式", "Settlement"),
      value: L(lang, spec.settlement, spec.settlementEn),
      note: L(lang, spec.settlementNote, spec.settlementNoteEn),
      icon: "ri-exchange-dollar-line",
      tone: "accent",
    },
    {
      key: "deposit",
      label: L(lang, "保证金比例", "Deposit ratio"),
      value: L(lang, spec.deposit, spec.depositEn),
      note: L(lang, spec.depositNote, spec.depositNoteEn),
      icon: "ri-refund-2-line",
      tone: "secondary",
    },
    {
      key: "currency",
      label: L(lang, "结算币种", "Settlement currency"),
      value: currency,
      note: L(lang, "优先锁定本币或可对冲币种", "Prefer the local or a hedgeable currency"),
      icon: "ri-money-dollar-circle-line",
      tone: "accent",
    },
    {
      key: "validity",
      label: L(lang, "授信有效期", "Credit validity"),
      value: L(lang, spec.validity, spec.validityEn),
      note: L(lang, spec.validityNote, spec.validityNoteEn),
      icon: "ri-time-line",
      tone: "secondary",
    },
    {
      key: "monitoring",
      label: L(lang, "贷后监控", "Post-loan monitoring"),
      value: L(lang, spec.monitoring, spec.monitoringEn),
      note: L(lang, spec.monitoringNote, spec.monitoringNoteEn),
      icon: "ri-radar-line",
      tone: "primary",
    },
  ];

  // --- mitigation measures -------------------------------------------------
  const crossBorder = !company.country.includes("中国") && !/China/i.test(company.country);
  const mitigations: MitigationMeasure[] = [
    {
      id: "contract",
      title: L(lang, "合同与账期条款约束", "Contract & tenor clauses"),
      detail: L(
        lang,
        `在购销合同中约定${spec.tenor}账期、逾期违约金、债权提前到期与管辖条款，将信用条件固化为合同义务。`,
        `Stipulate the ${spec.tenorEn} tenor, late-payment penalty, acceleration and jurisdiction clauses in the sales contract, fixing credit terms as contractual obligations.`,
      ),
      icon: "ri-file-text-line",
      requirement: "standard",
    },
  ];

  if (risk !== "low") {
    mitigations.push({
      id: "guarantee-person",
      title: L(lang, "实际控制人连带责任保证", "Joint-liability guarantee from controller"),
      detail: L(
        lang,
        `要求实际控制人 ${fActualController} 提供无限连带责任保证，并签署征信查询授权，形成第二还款来源。`,
        `Require the actual controller ${fActualController} to provide an unlimited joint-liability guarantee and sign a credit-inquiry authorization, forming a secondary repayment source.`,
      ),
      icon: "ri-user-follow-line",
      requirement: "required",
    });
  }

  mitigations.push(
    guarantorCount > 0
      ? {
          id: "guarantee-cap",
          title: L(lang, "关联担保限额与反担保", "Related-guarantee cap & counter-guarantee"),
          detail: L(
            lang,
            `对已存在的 ${guarantorCount} 项关联担保设置总额上限，并要求被担保方提供反担保或资产抵押，避免风险沿关联网络传导。`,
            `Set an aggregate cap on the ${guarantorCount} existing related guarantees and require counter-guarantees or asset collateral from guaranteed parties to prevent contagion across the network.`,
          ),
          icon: "ri-shield-cross-line",
          requirement: risk === "high" ? "required" : "recommended",
        }
      : {
          id: "guarantee-cap",
          title: L(lang, "关联交易持续披露", "Ongoing related-transaction disclosure"),
          detail: L(
            lang,
            "约定关联交易与对外担保的持续披露义务，触发阈值时提前还款或补充增信。",
            "Stipulate ongoing disclosure of related transactions and external guarantees; trigger early repayment or additional enhancement at thresholds.",
          ),
          icon: "ri-shield-cross-line",
          requirement: "standard",
        },
  );

  mitigations.push(
    collateral >= 70
      ? {
          id: "collateral",
          title: L(lang, "房产与设备抵押登记", "Property & equipment mortgage registration"),
          detail: L(
            lang,
            `可抵押资产覆盖充足（5C 担保维度 ${collateral}/100），建议办理厂房与设备抵押登记，形成有效第二还款来源。`,
            `Collateral coverage is ample (5C collateral ${collateral}/100); register mortgages on the plant and equipment as an effective secondary repayment source.`,
          ),
          icon: "ri-home-office-line",
          requirement: risk === "low" ? "recommended" : "required",
        }
      : {
          id: "collateral",
          title: L(lang, "应收账款质押 / 保理", "Receivables pledge / factoring"),
          detail: L(
            lang,
            `固定资产抵押空间有限（5C 担保维度 ${collateral}/100），建议以应收账款质押或保理方式增信，并设置回款专户。`,
            `Fixed-asset mortgage room is limited (5C collateral ${collateral}/100); enhance via receivables pledge or factoring and set up a dedicated collection account.`,
          ),
          icon: "ri-file-shield-2-line",
          requirement: "recommended",
        },
  );

  if (crossBorder) {
    mitigations.push({
      id: "insurance",
      title: L(lang, "出口信用保险与跨境结算", "Export credit insurance & cross-border settlement"),
      detail: L(
        lang,
        `注册地 ${country}，建议投保出口信用保险覆盖政治与商业风险，并优先采用信用证或人民币跨境结算。`,
        `Registered in ${country}; take out export credit insurance to cover political and commercial risk, and prefer LC or RMB cross-border settlement.`,
      ),
      icon: "ri-flight-takeoff-line",
      requirement: risk === "high" ? "required" : "recommended",
    });
  }

  if (risk === "high") {
    mitigations.push({
      id: "prepay",
      title: L(lang, "预付款与保证金", "Prepayment & deposit"),
      detail: L(
        lang,
        "新增业务采用预付款或全额保证金方式，不新增信用敞口，存量业务按计划逐步压退。",
        "Use prepayment or a full deposit for new business to avoid new exposure, and wind down existing business as planned.",
      ),
      icon: "ri-refund-2-line",
      requirement: "required",
    });
  }

  mitigations.push({
    id: "monitor",
    title: L(lang, "贷后动态监测", "Dynamic post-loan monitoring"),
    detail: L(
      lang,
      `接入「${spec.monitoring}」机制，对财报、工商变更、司法与舆情信号实时预警，触发风险信号时立即冻结额度。`,
      `Adopt "${spec.monitoringEn}" with real-time alerts on financials, registration changes, judicial and sentiment signals, freezing the limit immediately on a risk trigger.`,
    ),
    icon: "ri-radar-line",
    requirement: "standard",
  });

  // --- hit rules -----------------------------------------------------------
  const rules: DecisionRule[] = [];

  const pushRule = (input: RuleInput) => {
    rules.push(input);
  };

  const scoreSeverity: DecisionRuleSeverity =
    company.creditScore >= 600
      ? "pass"
      : company.creditScore >= 540
        ? "warn"
        : "block";
  pushRule({
    id: "score",
    code: "R-ACC-01",
    name: L(lang, "综合信用评分准入", "Composite credit score admission"),
    category: "准入",
    categoryEn: "Admission",
    severity: scoreSeverity,
    condition: L(
      lang,
      "信用评分 ≥ 600 分准予授信；540–599 分须附条件；低于 540 分拒入。",
      "Score ≥ 600 approved; 540–599 conditional; below 540 rejected.",
    ),
    actual: L(
      lang,
      `${company.creditScore} 分（${detail.grade} 级）`,
      `${company.creditScore} (grade ${detail.grade})`,
    ),
    action:
      scoreSeverity === "pass"
        ? L(lang, "按标准授信流程办理", "Proceed on the standard underwriting flow")
        : scoreSeverity === "warn"
          ? L(lang, "追加增信措施后方可授信", "Underwrite only after adding credit enhancement")
          : L(lang, "暂不受理新增授信", "Do not accept new credit for now"),
    desc: L(
      lang,
      `模型 ${detail.modelVersion} 给出 ${company.creditScore} 分，位于全库 P${detail.riskPercentile}，风险等级判定为${riskText}。`,
      `Model ${detail.modelVersion} gives ${company.creditScore}, at library P${detail.riskPercentile}, risk level ${riskText}.`,
    ),
  });

  const judicialHigh = highFlags.filter((flag) =>
    /信用|法务|合规/.test(flag.category),
  ).length;
  const judicialMid = midFlags.filter((flag) =>
    /信用|法务|合规/.test(flag.category),
  ).length;
  const judicialSeverity: DecisionRuleSeverity =
    judicialHigh > 0 ? "block" : judicialMid > 0 ? "warn" : "pass";
  pushRule({
    id: "judicial",
    code: "R-ACC-02",
    name: L(lang, "失信与被执行记录", "Enforcement & dishonesty records"),
    category: "准入",
    categoryEn: "Admission",
    severity: judicialSeverity,
    condition: L(
      lang,
      "无被执行、严重失信与被列入经营异常名录记录。",
      "No enforcement, serious dishonesty or abnormal-operation listing records.",
    ),
    actual:
      judicialHigh > 0
        ? L(
            lang,
            `命中高风险 ${judicialHigh} 项 / 中风险 ${judicialMid} 项`,
            `${judicialHigh} high / ${judicialMid} medium hit`,
          )
        : judicialMid > 0
          ? L(
              lang,
              `无高风险，中风险关注项 ${judicialMid} 项`,
              `No high risk, ${judicialMid} medium watch items`,
            )
          : L(lang, "未命中负面记录", "No negative records hit"),
    action:
      judicialSeverity === "block"
        ? L(lang, "暂不受理，待记录清除后重新评估", "Decline until the records are cleared, then re-assess")
        : judicialSeverity === "warn"
          ? L(lang, "补充法务尽调并追加担保", "Add legal due diligence and extra guarantees")
          : L(lang, "按标准流程办理", "Proceed on the standard flow"),
    desc: L(
      lang,
      "基于司法执行、失信被执行人、经营异常与行政处罚多源数据联合扫描的准入底线规则。",
      "A baseline admission rule scanning enforcement, dishonest debtors, abnormal-operation and administrative penalties.",
    ),
  });

  const ratingWarn = /负面|暂无|无有效|CCC|CC|negative|n\/a|none/i.test(factOr(facts.ratingAgency, factsEn?.ratingAgency));
  pushRule({
    id: "rating",
    code: "R-ACC-03",
    name: L(lang, "外部评级要求", "External rating requirement"),
    category: "准入",
    categoryEn: "Admission",
    severity: ratingWarn ? "warn" : "pass",
    condition: L(
      lang,
      "外部信用评级不低于 BB，且评级展望非负面。",
      "External rating not below BB and outlook not negative.",
    ),
    actual: fRatingAgency,
    action: ratingWarn
      ? L(lang, "提高保证金额度并缩短账期", "Raise the deposit and shorten the tenor")
      : L(lang, "按标准条件办理", "Proceed on standard terms"),
    desc: L(
      lang,
      "外部评级作为模型输出的交叉验证，评级缺失或展望负面的主体需人工复核。",
      "External ratings cross-validate the model output; entities with a missing rating or negative outlook need manual review.",
    ),
  });

  const paidSeverity: DecisionRuleSeverity =
    paidRatio >= 80 ? "pass" : paidRatio >= 50 ? "warn" : "block";
  pushRule({
    id: "paid-in",
    code: "R-CAP-01",
    name: L(lang, "注册资本实缴比例", "Paid-in capital ratio"),
    category: "额度",
    categoryEn: "Limit",
    severity: paidSeverity,
    condition: L(
      lang,
      "注册资本实缴比例 ≥ 80%；低于 50% 视为权益缓冲不足。",
      "Paid-in ratio ≥ 80%; below 50% is treated as insufficient equity buffer.",
    ),
    actual: L(lang, `实缴 ${paidRatio}%`, `Paid-in ${paidRatio}%`),
    action:
      paidSeverity === "pass"
        ? L(lang, "按测算额度执行", "Execute the calculated limit")
        : paidSeverity === "warn"
          ? L(lang, "要求限期补足实缴后再放款", "Require top-up of paid-in capital before disbursing")
          : L(lang, "要求足额实缴或追加股东担保", "Require full paid-in or additional shareholder guarantees"),
    desc: L(
      lang,
      `实缴资本 ${fPaidInCapital}，实缴比例越高，股东承诺的可信度与权益缓冲越强。`,
      `Paid-in capital ${fPaidInCapital}; a higher ratio means stronger shareholder commitment and equity buffer.`,
    ),
  });

  const guaranteeRatioText =
    risk === "low" ? "4.1%" : risk === "medium" ? "24.0%" : "38.6%";
  const guaranteeSeverity: DecisionRuleSeverity =
    risk === "low" ? "pass" : risk === "medium" ? "warn" : "block";
  pushRule({
    id: "guarantee-ratio",
    code: "R-CAP-02",
    name: L(lang, "关联担保敞口占比", "Related-guarantee exposure ratio"),
    category: "额度",
    categoryEn: "Limit",
    severity: guaranteeSeverity,
    condition: L(
      lang,
      "对外担保余额不超过净资产的 20%。",
      "External guarantee balance ≤ 20% of net assets.",
    ),
    actual: L(lang, `占净资产 ${guaranteeRatioText}`, `${guaranteeRatioText} of net assets`),
    action:
      guaranteeSeverity === "pass"
        ? L(lang, "按测算额度执行", "Execute the calculated limit")
        : guaranteeSeverity === "warn"
          ? L(lang, "要求担保总额设上限并补充反担保", "Cap the total guarantee and require counter-guarantees")
          : L(lang, "要求优先压降存量担保后再评估", "Require reducing existing guarantees before re-assessing"),
    desc: L(
      lang,
      "关联担保会放大风险在集团内部的传导，是额度测算中最重要的扣减项之一。",
      "Related guarantees amplify risk contagion within the group and are one of the biggest deductions in sizing.",
    ),
  });

  const concentrationText =
    risk === "low" ? "38.4%" : risk === "medium" ? "52.6%" : "71.2%";
  const concentrationSeverity: DecisionRuleSeverity =
    risk === "low" ? "pass" : "warn";
  pushRule({
    id: "concentration",
    code: "R-CAP-03",
    name: L(lang, "客户集中度控制", "Customer concentration control"),
    category: "额度",
    categoryEn: "Limit",
    severity: concentrationSeverity,
    condition: L(
      lang,
      "前五大客户收入占比 ≤ 50%，单一客户 ≤ 30%。",
      "Top-5 customer revenue ≤ 50%, single customer ≤ 30%.",
    ),
    actual: L(lang, `前五大客户占比 ${concentrationText}`, `Top-5 customers ${concentrationText}`),
    action:
      concentrationSeverity === "pass"
        ? L(lang, "按测算额度执行", "Execute the calculated limit")
        : L(lang, "设定单一客户回款上限并加强账龄管理", "Cap per-customer collections and tighten aging management"),
    desc: L(
      lang,
      "客户集中度直接决定收入波动性与回款稳定性，是额度测算的规模约束条件。",
      "Customer concentration directly drives revenue volatility and collection stability, constraining sizing.",
    ),
  });

  pushRule({
    id: "tenor",
    code: "R-TRM-01",
    name: L(lang, "最高付款账期", "Maximum payment tenor"),
    category: "账期",
    categoryEn: "Tenor",
    severity: risk === "low" ? "pass" : "warn",
    condition: L(
      lang,
      "付款账期不超过 90 天；中高风险主体账期不超过 45 天。",
      "Tenor ≤ 90 days; ≤ 45 days for medium/high-risk entities.",
    ),
    actual: L(lang, spec.tenor, spec.tenorEn),
    action:
      risk === "low"
        ? L(lang, "按标准账期执行", "Execute the standard tenor")
        : L(lang, "按压缩账期执行并跟踪回款", "Execute the compressed tenor and track collections"),
    desc: L(
      lang,
      "账期越长，形成的信用敞口越大，需与主体风险等级相匹配。",
      "A longer tenor creates a larger credit exposure and must match the entity's risk level.",
    ),
  });

  pushRule({
    id: "guarantee-required",
    code: "R-GRT-01",
    name: L(lang, "增信措施要求", "Credit enhancement requirement"),
    category: "担保",
    categoryEn: "Guarantee",
    severity: risk === "low" ? "pass" : risk === "medium" ? "warn" : "block",
    condition: L(
      lang,
      "中风险主体须追加连带责任保证；高风险主体须足额抵押或保证金。",
      "Medium-risk entities need a joint-liability guarantee; high-risk entities need full collateral or deposit.",
    ),
    actual: L(lang, `${riskText}主体`, `${riskText} entity`),
    action:
      risk === "low"
        ? L(lang, "可信用方式放款", "Disburse on trust")
        : risk === "medium"
          ? L(lang, "落实连保证与抵押登记后放款", "Disburse after joint guarantee and mortgage registration")
          : L(lang, "以预付款 / 保证金方式办理", "Handle via prepayment / deposit"),
    desc: L(
      lang,
      "增信措施直接决定违约损失率（LGD），是缓释信用风险的核心手段。",
      "Credit enhancement directly drives the loss given default (LGD) and is the core risk-mitigation tool.",
    ),
  });

  const watchHit = WATCH_COUNTRIES.some((name) => company.country.includes(name));
  pushRule({
    id: "country",
    code: "R-CNY-01",
    name: L(lang, "国别风险折减", "Country risk discount"),
    category: "国别",
    categoryEn: "Country",
    severity: watchHit ? "warn" : "pass",
    condition: L(
      lang,
      "注册地不属于高风险 / 受制裁 / 外汇管制关注国别。",
      "Registered in a country that is not high-risk / sanctioned / on the FX-control watchlist.",
    ),
    actual: country,
    action: watchHit
      ? L(lang, "要求投保出口信用保险并采用信用证结算", "Require export credit insurance and LC settlement")
      : L(lang, "按标准流程办理", "Proceed on the standard flow"),
    desc: L(
      lang,
      "国别风险通过汇率、外汇管制与地缘政治影响回款，是跨境授信的必要折减项。",
      "Country risk affects collections through FX, capital controls and geopolitics, a necessary discount for cross-border credit.",
    ),
  });

  const pdSeverity: DecisionRuleSeverity =
    company.defaultProb <= 8
      ? "pass"
      : company.defaultProb <= 14
        ? "warn"
        : "block";
  pushRule({
    id: "pd",
    code: "R-MDL-01",
    name: L(lang, "违约概率阈值", "Default probability threshold"),
    category: "模型",
    categoryEn: "Model",
    severity: pdSeverity,
    condition: L(
      lang,
      "12 个月违约概率 ≤ 8% 通过；8%–14% 提示；高于 14% 拦截。",
      "12-month default probability ≤ 8% pass; 8%–14% warn; above 14% block.",
    ),
    actual: L(
      lang,
      `${company.defaultProb.toFixed(1)}%（基准 ${detail.pdBase.toFixed(1)}%）`,
      `${company.defaultProb.toFixed(1)}% (base ${detail.pdBase.toFixed(1)}%)`,
    ),
    action:
      pdSeverity === "pass"
        ? L(lang, "按测算额度执行", "Execute the calculated limit")
        : pdSeverity === "warn"
          ? L(lang, "追加增信并缩短账期", "Add enhancement and shorten the tenor")
          : L(lang, "暂停新增授信", "Suspend new credit"),
    desc: L(
      lang,
      `违约概率由模型 ${detail.modelVersion} 输出，是额度与账期定价的直接依据。`,
      `The default probability comes from model ${detail.modelVersion} and directly drives limit and tenor pricing.`,
    ),
  });

  pushRule({
    id: "monitoring",
    code: "R-MON-01",
    name: L(lang, "贷后监控指标", "Post-loan monitoring metrics"),
    category: "监控",
    categoryEn: "Monitoring",
    severity: "pass",
    condition: L(
      lang,
      "授信存续期须接入财报、工商、司法与舆情实时监测。",
      "During the credit term, real-time monitoring of financials, registry, judicial and sentiment is required.",
    ),
    actual: L(lang, spec.monitoring, spec.monitoringEn),
    action: L(
      lang,
      "按约定频率执行贷后监控并留痕",
      "Run post-loan monitoring at the agreed frequency with a full trail",
    ),
    desc: L(
      lang,
      "贷后监控用于及时发现评级迁徙与风险信号变化，触发条件时自动冻结额度。",
      "Post-loan monitoring detects rating migration and risk-signal changes, auto-freezing the limit on a trigger.",
    ),
  });

  const warnCount = rules.filter((rule) => rule.severity === "warn").length;
  const blockCount = rules.filter((rule) => rule.severity === "block").length;
  const passCount = rules.filter((rule) => rule.severity === "pass").length;
  const approver = APPROVERS[hash(company.id) % APPROVERS.length];

  return {
    id: `DEC-${company.id}`,
    outcome,
    outcomeLabel: L(lang, outcomeMeta.label, outcomeMeta.labelEn),
    outcomeNote: L(lang, outcomeMeta.note, outcomeMeta.noteEn),
    symbol,
    limitLabel,
    creditLimit: company.creditLimit,
    limitNumeric,
    baseLimit: formatMoney(symbol, baseAmount),
    baseRatio: baseAmount / limitNumeric,
    adjustmentDisplay: `${adjustSum >= 0 ? "+" : "−"}${formatMoney(symbol, Math.abs(adjustSum))}`,
    adjustmentPositive: adjustSum >= 0,
    bands,
    factors,
    terms,
    mitigations,
    rules,
    hitCount: warnCount + blockCount,
    warnCount,
    blockCount,
    passCount,
    approver: isEn ? approver.en : approver.zh,
    decidedAt: company.updatedAt,
    validUntil: addMonths(company.updatedAt, spec.validityMonths),
    modelVersion: detail.modelVersion,
  };
}

/** Uses the English rating when available so negative-outlook detection still works in EN. */
function factOr(zh: string, en?: string): string {
  return `${zh} ${en ?? ""}`;
}