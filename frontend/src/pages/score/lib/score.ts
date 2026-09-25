import type {
  CommunityBenchmark,
  Company,
  CompanyProfile,
  RiskFlag,
  RiskLevel,
  ScoreDetail,
  ShapFeature,
} from "@/types";

export type Lang = "zh" | "en";

const L = (lang: Lang, zh: string, en: string): string =>
  lang === "en" ? en : zh;

/** Model expected output (dataset prior) — every waterfall starts here. */
export const BASE_VALUE = 640;
export const SCORE_MIN = 300;
export const SCORE_MAX = 850;
export const MODEL_VERSION = "v4.2.0";
export const PD_BASE = 7.6;

const BASE_FLAG_WEIGHT = 12;

const CATEGORY_TO_FEATURE: Record<string, string> = {
  信用风险: "credit",
  合规表现: "compliance",
  法务风险: "compliance",
  治理风险: "governance",
  担保风险: "guarantee",
  经营风险: "operation",
  供应链风险: "operation",
  运营风险: "operation",
  财务风险: "capital",
  市场风险: "environment",
  资本风险: "capital",
};

export const GRADE_BANDS: {
  min: number;
  grade: string;
  note: string;
  noteEn: string;
}[] = [
  {
    min: 800,
    grade: "AAA",
    note: "偿付能力极强，违约风险极低",
    noteEn: "Very strong solvency, minimal default risk",
  },
  {
    min: 760,
    grade: "AA",
    note: "偿付能力强，违约风险很低",
    noteEn: "Strong solvency, very low default risk",
  },
  {
    min: 720,
    grade: "A",
    note: "偿付能力较强，违约风险较低",
    noteEn: "Good solvency, low default risk",
  },
  {
    min: 680,
    grade: "BBB",
    note: "偿付能力一般，需关注不利变化",
    noteEn: "Adequate solvency, watch for adverse changes",
  },
  {
    min: 640,
    grade: "BB",
    note: "存在一定违约风险，建议追加增信",
    noteEn: "Some default risk, add credit enhancement",
  },
  {
    min: 600,
    grade: "B",
    note: "违约风险较高，需强化担保措施",
    noteEn: "Elevated default risk, strengthen guarantees",
  },
  {
    min: 560,
    grade: "CCC",
    note: "违约风险高，建议限制授信额度",
    noteEn: "High default risk, cap the credit limit",
  },
  {
    min: 0,
    grade: "CC",
    note: "违约风险极高，建议拒贷或仅信用证",
    noteEn: "Very high default risk, decline or LC only",
  },
];

function hash(input: string): number {
  let value = 0;
  for (let i = 0; i < input.length; i += 1) {
    value = (value * 31 + input.charCodeAt(i)) >>> 0;
  }
  return value;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

function severity(level: RiskLevel): number {
  if (level === "high") return 1;
  if (level === "medium") return 0.45;
  return 0.1;
}

function groupFlags(flags: RiskFlag[]): Record<string, RiskFlag[]> {
  const groups: Record<string, RiskFlag[]> = {};
  flags.forEach((flag) => {
    const key = CATEGORY_TO_FEATURE[flag.category] ?? "operation";
    if (!groups[key]) groups[key] = [];
    groups[key].push(flag);
  });
  return groups;
}

function employeeCount(text: string): number {
  const digits = text.replace(/[^0-9]/g, "");
  return digits ? Number(digits) : 0;
}

function dimensionScore(profile: CompanyProfile, key: string): number {
  return profile.fiveC.find((item) => item.key === key)?.score ?? 62;
}

function sizeTier(employees: number, lang: Lang): string {
  if (employees >= 2000) return L(lang, "大型企业", "Large enterprise");
  if (employees >= 500) return L(lang, "中型企业", "Mid-sized enterprise");
  if (employees >= 100) return L(lang, "中小型企业", "SME");
  return L(lang, "小微企业", "Micro enterprise");
}

function pdForScore(score: number): number {
  return round1(clamp(0.6 + Math.exp(-(score - 560) / 70) * 22, 0.3, 32));
}

export function gradeFor(
  score: number,
  lang: Lang = "zh",
): { grade: string; note: string } {
  const hit =
    GRADE_BANDS.find((band) => score >= band.min) ??
    GRADE_BANDS[GRADE_BANDS.length - 1];
  return { grade: hit.grade, note: lang === "en" ? hit.noteEn : hit.note };
}

interface RawFeature {
  id: string;
  label: string;
  category: string;
  value: string;
  raw: number;
  desc: string;
}

function buildRawFeatures(
  company: Company,
  profile: CompanyProfile,
  lang: Lang,
): RawFeature[] {
  const groups = groupFlags(profile.riskFlags);
  const penalty = (key: string) =>
    (groups[key] ?? []).reduce(
      (sum, flag) => sum + severity(flag.level) * BASE_FLAG_WEIGHT,
      0,
    );

  const character = dimensionScore(profile, "character");
  const capacity = dimensionScore(profile, "capacity");
  const capital = dimensionScore(profile, "capital");
  const collateral = dimensionScore(profile, "collateral");
  const environment = dimensionScore(profile, "environment");

  const { facts } = profile;
  const factsEn = profile.factsEn;
  const isEn = lang === "en";
  const ratingAgency = isEn ? (factsEn?.ratingAgency ?? facts.ratingAgency) : facts.ratingAgency;
  const netMargin = isEn ? (factsEn?.netMargin ?? facts.netMargin) : facts.netMargin;
  const revenue = isEn ? (factsEn?.revenue ?? facts.revenue) : facts.revenue;
  const controllerStake = isEn
    ? (factsEn?.controllerStake ?? facts.controllerStake)
    : facts.controllerStake;
  const actualController = isEn
    ? (factsEn?.actualController ?? facts.actualController)
    : facts.actualController;
  const employeesText = isEn ? (factsEn?.employees ?? facts.employees) : facts.employees;

  const country = isEn ? (company.countryEn ?? company.country) : company.country;
  const industry = isEn ? (company.industryEn ?? company.industry) : company.industry;

  const employees = employeeCount(profile.facts.employees);
  const age = Math.max(1, 2026 - Number(profile.facts.established.slice(0, 4)));

  const complianceCount = (groups.compliance ?? []).length;
  const operationCount = (groups.operation ?? []).length;
  const guaranteeCount = (groups.guarantee ?? []).length;

  return [
    {
      id: "credit",
      label: L(lang, "履约与信用记录", "Payment & credit records"),
      category: L(lang, "信用与履约", "Credit & performance"),
      value: ratingAgency,
      raw: (character - 55) * 0.5 - penalty("credit"),
      desc: L(
        lang,
        `外部信用记录与历史履约表现。信誉维度评分 ${character}/100，外部评级口径：${ratingAgency}。`,
        `External credit records and historical performance. Character dimension ${character}/100, external rating: ${ratingAgency}.`,
      ),
    },
    {
      id: "compliance",
      label: L(lang, "涉诉与合规表现", "Litigation & compliance"),
      category: L(lang, "合规与法务", "Compliance & legal"),
      value:
        complianceCount === 0
          ? L(lang, "未命中负面记录", "No negative records hit")
          : L(
              lang,
              `${complianceCount} 项法务 / 合规信号`,
              `${complianceCount} legal / compliance signals`,
            ),
      raw: 6 - penalty("compliance"),
      desc:
        complianceCount === 0
          ? L(
              lang,
              "近三年未命中被执行、重大诉讼与合规处罚记录，合规维度表现稳定。",
              "No enforcement, major litigation or compliance penalties in the past three years; compliance performance is stable.",
            )
          : L(
              lang,
              `命中 ${complianceCount} 项法务 / 合规信号，已按严重程度折减评分贡献。`,
              `${complianceCount} legal / compliance signals hit; the score contribution is reduced by severity.`,
            ),
    },
    {
      id: "capacity",
      label: L(lang, "经营与订单能力", "Operating & order capacity"),
      category: L(lang, "经营能力", "Operating capacity"),
      value: L(lang, `能力维度 ${capacity} / 100`, `Capacity ${capacity} / 100`),
      raw: (capacity - 55) * 0.5,
      desc: L(
        lang,
        "订单能见度、产能利用率与交付准时率共同构成的经营性能力信号。",
        "A signal formed by order visibility, capacity utilization and on-time delivery.",
      ),
    },
    {
      id: "capital",
      label: L(lang, "资本结构与杠杆", "Capital structure & leverage"),
      category: L(lang, "资本与财务", "Capital & finance"),
      value: netMargin,
      raw: (capital - 55) * 0.5 - penalty("capital"),
      desc: L(
        lang,
        `资产负债结构、现金流覆盖与盈利水平。${revenue}；${netMargin}。`,
        `Balance-sheet structure, cash-flow coverage and profitability. ${revenue}; ${netMargin}.`,
      ),
    },
    {
      id: "guarantee",
      label: L(lang, "关联方与对外担保", "Related parties & guarantees"),
      category: L(lang, "担保与抵押", "Guarantee & collateral"),
      value:
        guaranteeCount === 0
          ? L(lang, "无重大对外担保", "No major external guarantees")
          : L(lang, `${guaranteeCount} 项担保信号`, `${guaranteeCount} guarantee signals`),
      raw: (collateral - 55) * 0.4 - penalty("guarantee"),
      desc: L(
        lang,
        "关联方敞口、对外担保规模与抵押物覆盖能力的综合评估。",
        "A combined assessment of related-party exposure, external guarantee scale and collateral coverage.",
      ),
    },
    {
      id: "governance",
      label: L(lang, "治理与股权稳定性", "Governance & equity stability"),
      category: L(lang, "治理结构", "Governance"),
      value: controllerStake,
      raw: 5 - penalty("governance"),
      desc: L(
        lang,
        `股权结构稳定性与控制权集中度。${controllerStake}，实际控制人为 ${actualController}。`,
        `Equity stability and control concentration. ${controllerStake}, actual controller ${actualController}.`,
      ),
    },
    {
      id: "operation",
      label: L(lang, "客户与供应链集中度", "Customer & supply-chain concentration"),
      category: L(lang, "客户与供应链", "Customers & supply chain"),
      value:
        operationCount === 0
          ? L(lang, "集中度处于合理区间", "Concentration within a reasonable range")
          : L(
              lang,
              `${operationCount} 项集中度信号`,
              `${operationCount} concentration signals`,
            ),
      raw: 5 - penalty("operation") * 0.8,
      desc: L(
        lang,
        "客户集中度、供应商依赖与供应链稳定性的综合表现。",
        "A combined view of customer concentration, supplier dependency and supply-chain stability.",
      ),
    },
    {
      id: "environment",
      label: L(lang, "行业与国别环境", "Industry & country environment"),
      category: L(lang, "行业与国别", "Industry & country"),
      value: `${country} · ${company.sector}`,
      raw: (environment - 55) * 0.4 - penalty("environment") * 0.6,
      desc: L(
        lang,
        `所处行业景气度与国别宏观风险。主营 ${industry}，注册地 ${country}。`,
        `Industry cycle and country macro risk. Core business ${industry}, registered in ${country}.`,
      ),
    },
    {
      id: "scale",
      label: L(lang, "企业规模与经营年限", "Scale & years in business"),
      category: L(lang, "规模与年限", "Scale & vintage"),
      value: L(lang, `员工 ${employeesText}`, `Employees ${employeesText}`),
      raw: clamp((age - 8) * 0.8, -6, 9) + clamp(employees / 600, 0, 8) - 5,
      desc: L(
        lang,
        `成立于 ${facts.established}，已持续经营 ${age} 年，人员规模 ${employeesText}，形成规模与存续期稳定性溢价。`,
        `Founded ${facts.established}, operating ${age} years, ${employeesText} staff, earning a scale-and-vintage stability premium.`,
      ),
    },
  ];
}

function buildFeatures(
  company: Company,
  profile: CompanyProfile,
  lang: Lang,
): ShapFeature[] {
  const raws = buildRawFeatures(company, profile, lang);
  const targetDelta = company.creditScore - BASE_VALUE;
  const sumRaw = raws.reduce((sum, item) => sum + item.raw, 0);
  const scale = Math.abs(sumRaw) < 0.001 ? 0 : targetDelta / sumRaw;

  const features: ShapFeature[] = raws.map((item) => ({
    id: item.id,
    label: item.label,
    category: item.category,
    value: item.value,
    desc: item.desc,
    contribution: round1(item.raw * scale),
  }));

  // Correct rounding drift on the most influential feature so the sum is exact.
  const drift = round1(
    targetDelta - features.reduce((sum, item) => sum + item.contribution, 0),
  );
  if (Math.abs(drift) >= 0.05) {
    let index = 0;
    features.forEach((item, i) => {
      if (Math.abs(item.contribution) > Math.abs(features[index].contribution))
        index = i;
    });
    features[index] = {
      ...features[index],
      contribution: round1(features[index].contribution + drift),
    };
  }

  return [...features].sort((a, b) => b.contribution - a.contribution);
}

function buildBenchmarks(
  company: Company,
  profile: CompanyProfile,
  lang: Lang,
): CommunityBenchmark[] {
  const seed = hash(company.id);
  const score = company.creditScore;
  const employees = employeeCount(profile.facts.employees);

  const groups = [
    {
      key: "sector",
      label: L(lang, "同行业", "Sector peers"),
      tag: company.sector,
      n: 186 + (seed % 240),
    },
    {
      key: "country",
      label: L(lang, "同国别 / 地区", "Same country / region"),
      tag: company.region,
      n: 92 + (seed % 150),
    },
    {
      key: "size",
      label: L(lang, "同规模", "Same size"),
      tag: sizeTier(employees, lang),
      n: 210 + (seed % 280),
    },
    {
      key: "all",
      label: L(lang, "全库基准", "Library benchmark"),
      tag: L(lang, "全体在库样本", "All sampled firms"),
      n: 4820 + (seed % 600),
    },
  ];

  return groups.map((group, index) => {
    const offset = ((seed >> ((index + 1) * 3)) % 90) - 45;
    const pull = group.key === "all" ? 0.16 : 0.32;
    const avgScore = clamp(
      Math.round(BASE_VALUE + (score - BASE_VALUE) * pull + offset),
      400,
      830,
    );
    const std = 48 + ((seed >> (index * 2)) % 30);
    const percentile = clamp(
      Math.round(100 / (1 + Math.exp((-1.7 * (score - avgScore)) / std))),
      1,
      99,
    );
    const avgDefaultProb = round1(
      clamp(company.defaultProb * Math.exp((score - avgScore) / 110), 0.2, 30),
    );
    const goodRate = clamp(Math.round((avgScore - 470) / 3.4), 4, 94);

    return {
      key: group.key,
      label: group.label,
      tag: group.tag,
      sampleSize: group.n,
      avgScore,
      avgDefaultProb,
      percentile,
      goodRate,
      diff: score - avgScore,
    };
  });
}

export function buildScoreDetail(
  company: Company,
  profile: CompanyProfile,
  lang: Lang = "zh",
): ScoreDetail {
  const seed = hash(company.id);
  const features = buildFeatures(company, profile, lang);
  const benchmarks = buildBenchmarks(company, profile, lang);
  const all =
    benchmarks.find((item) => item.key === "all") ??
    benchmarks[benchmarks.length - 1];
  const { grade, note } = gradeFor(company.creditScore, lang);

  return {
    baseValue: BASE_VALUE,
    finalScore: company.creditScore,
    grade,
    gradeNote: note,
    riskPercentile: all.percentile,
    defaultProb: company.defaultProb,
    pdBase: PD_BASE,
    pdDelta: round1(company.defaultProb - PD_BASE),
    confidence: 88 + (seed % 9),
    modelVersion: MODEL_VERSION,
    evaluatedAt: company.updatedAt,
    positiveCount: features.filter((item) => item.contribution > 0).length,
    negativeCount: features.filter((item) => item.contribution < 0).length,
    features,
    benchmarks,
  };
}

export function formatContribution(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

export { pdForScore };