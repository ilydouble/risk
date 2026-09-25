import type {
  AblationRow,
  AblationStudy,
  CalibrationBin,
  CalibrationCurve,
  EvalDashboard,
  EvalMetric,
  ExtrapolationCohort,
  ExtrapolationRow,
  ExtrapolationStudy,
  ReproduceRun,
  ReproduceStep,
} from "@/entities/demo/model/types";
import { modelVersionHistory } from "@/features/demo-scenarios/model/fixtures/modelCard";

export const EVAL_MODEL_VERSION = "v4.2.0";

export type Lang = "zh" | "en";

const L = (lang: Lang, zh: string, en: string): string =>
  lang === "en" ? en : zh;

/* ------------------------------------------------------------------ */
/* Version profiles                                                    */
/* ------------------------------------------------------------------ */

const VERSION_RANK: Record<string, number> = {
  "v3.8.0": 1,
  "v3.9.0": 2,
  "v4.0.0": 3,
  "v4.2.0": 4,
};

/** 由新到旧，与版本演进史保持同一顺序。 */
export const EVAL_VERSIONS: string[] = modelVersionHistory.map(
  (entry) => entry.version,
);

export function isEvalVersion(value: string | null | undefined): boolean {
  return typeof value === "string" && EVAL_VERSIONS.includes(value);
}

interface VersionProfile {
  version: string;
  trainedAt: string;
  validatedAt: string;
  datasetSize: number;
  featureCount: number;
  positiveRate: number;
  /** 校准曲线相对当前版本的偏离倍数，1 表示与生产版一致。 */
  calibScale: number;
  calibrationBrier: number;
  /** 每项取值 [上一版本, 当前版本]。 */
  metrics: {
    auc: [number, number];
    ks: [number, number];
    lift: [number, number];
    brier: [number, number];
  };
}

const VERSION_PROFILES: Record<string, VersionProfile> = {
  "v4.2.0": {
    version: "v4.2.0",
    trainedAt: "2026-08-28",
    validatedAt: "2026-09-24 06:30",
    datasetSize: 52420,
    featureCount: 76,
    positiveRate: 0.074,
    calibScale: 1,
    calibrationBrier: 0.086,
    metrics: {
      auc: [0.858, 0.874],
      ks: [0.391, 0.412],
      lift: [3.14, 3.28],
      brier: [0.093, 0.086],
    },
  },
  "v4.0.0": {
    version: "v4.0.0",
    trainedAt: "2025-12-08",
    validatedAt: "2025-12-15 06:30",
    datasetSize: 47600,
    featureCount: 64,
    positiveRate: 0.074,
    calibScale: 1.14,
    calibrationBrier: 0.093,
    metrics: {
      auc: [0.851, 0.858],
      ks: [0.383, 0.391],
      lift: [3.01, 3.14],
      brier: [0.099, 0.093],
    },
  },
  "v3.9.0": {
    version: "v3.9.0",
    trainedAt: "2025-08-28",
    validatedAt: "2025-09-06 06:30",
    datasetSize: 41900,
    featureCount: 58,
    positiveRate: 0.073,
    calibScale: 1.28,
    calibrationBrier: 0.099,
    metrics: {
      auc: [0.846, 0.851],
      ks: [0.376, 0.383],
      lift: [2.92, 3.01],
      brier: [0.104, 0.099],
    },
  },
  "v3.8.0": {
    version: "v3.8.0",
    trainedAt: "2025-06-10",
    validatedAt: "2025-06-18 06:30",
    datasetSize: 38200,
    featureCount: 52,
    positiveRate: 0.071,
    calibScale: 1.42,
    calibrationBrier: 0.104,
    metrics: {
      auc: [0.838, 0.846],
      ks: [0.368, 0.376],
      lift: [2.86, 2.92],
      brier: [0.109, 0.104],
    },
  },
};

function resolveProfile(version: string): VersionProfile {
  return VERSION_PROFILES[version] ?? VERSION_PROFILES[EVAL_MODEL_VERSION];
}

/* ------------------------------------------------------------------ */
/* Metrics                                                             */
/* ------------------------------------------------------------------ */

type MetricKey = keyof VersionProfile["metrics"];

interface MetricMeta {
  key: MetricKey;
  label: string;
  fullLabel: string;
  fullLabelEn: string;
  decimals: number;
  higherBetter: boolean;
  target: number;
  ci: number;
  hint: string;
  hintEn: string;
  desc: (display: string, lang: Lang) => string;
}

const METRIC_META: MetricMeta[] = [
  {
    key: "auc",
    label: "AUC",
    fullLabel: "ROC 曲线下面积",
    fullLabelEn: "Area under the ROC curve",
    decimals: 3,
    higherBetter: true,
    target: 0.8,
    ci: 0.008,
    hint: "区分违约与非违约客户的整体排序能力",
    hintEn: "Overall ranking power separating defaulters from non-defaulters",
    desc: (display, lang) =>
      L(
        lang,
        `随机抽取一对违约 / 非违约样本，模型给违约方更高风险分的概率。当前版本为 ${display}，处于优秀的区分度区间。`,
        `The probability that, for a random pair of default / non-default samples, the model gives the defaulter a higher risk score. The current version is ${display}, in the excellent discrimination range.`,
      ),
  },
  {
    key: "ks",
    label: "KS",
    fullLabel: "Kolmogorov–Smirnov 统计量",
    fullLabelEn: "Kolmogorov–Smirnov statistic",
    decimals: 3,
    higherBetter: true,
    target: 0.35,
    ci: 0.011,
    hint: "正负样本累计分布的最大分离度",
    hintEn: "Maximum separation of the positive/negative cumulative distributions",
    desc: (display, lang) =>
      L(
        lang,
        `衡量模型将好坏样本区分开的最大距离，当前值 ${display}，即在最优切分点上可分离约 ${Math.round(
          parseFloat(display) * 100,
        )}% 的样本。`,
        `The maximum distance by which the model separates good and bad samples; the current value is ${display}, separating about ${Math.round(
          parseFloat(display) * 100,
        )}% of samples at the optimal cutoff.`,
      ),
  },
  {
    key: "lift",
    label: "Lift@10%",
    fullLabel: "前 10% 风险名单的提升倍数",
    fullLabelEn: "Lift of the top 10% risk list",
    decimals: 2,
    higherBetter: true,
    target: 2.5,
    ci: 0.12,
    hint: "头部名单相对随机抽样的风险提升",
    hintEn: "Risk uplift of the top list versus random sampling",
    desc: (display, lang) =>
      L(
        lang,
        `按风险分排序取前 10% 名单，其中违约客户占比是随机抽样的 ${display} 倍，用于优先安排人工尽调与审核。`,
        `Sorting by risk score, the top 10% list's defaulter share is ${display}× that of random sampling, used to prioritize manual due diligence and review.`,
      ),
  },
  {
    key: "brier",
    label: "Brier",
    fullLabel: "概率预测的均方误差",
    fullLabelEn: "Mean squared error of probability forecasts",
    decimals: 3,
    higherBetter: false,
    target: 0.1,
    ci: 0.003,
    hint: "违约概率校准后的整体预测误差",
    hintEn: "Overall forecast error after PD calibration",
    desc: (display, lang) =>
      L(
        lang,
        `越小越好，同时反映区分度与校准度。当前值 ${display}，预测违约概率整体贴近真实违约频率，可用于定价与额度测算。`,
        `Lower is better and reflects both discrimination and calibration. The current value is ${display}; predicted default probabilities sit close to the true default frequency and can be used for pricing and limit sizing.`,
      ),
  },
];

function signed(value: number, decimals: number): string {
  const text = Math.abs(value).toFixed(decimals);
  return `${value >= 0 ? "+" : "−"}${text}`;
}

function buildMetrics(profile: VersionProfile, lang: Lang): EvalMetric[] {
  return METRIC_META.map((meta) => {
    const [prev, value] = profile.metrics[meta.key];
    const delta = Number((value - prev).toFixed(meta.decimals));
    const status: EvalMetric["status"] = meta.higherBetter
      ? value >= meta.target
        ? "pass"
        : "watch"
      : value <= meta.target
        ? "pass"
        : "watch";
    const display = value.toFixed(meta.decimals);
    return {
      key: meta.key,
      label: meta.label,
      fullLabel: L(lang, meta.fullLabel, meta.fullLabelEn),
      value,
      display,
      prev,
      delta,
      deltaDisplay: signed(delta, meta.decimals),
      ci: meta.ci,
      ciRange: `${(value - meta.ci).toFixed(meta.decimals)} – ${(
        value + meta.ci
      ).toFixed(meta.decimals)}`,
      target: meta.target,
      targetDisplay: `${meta.higherBetter ? "≥" : "≤"} ${meta.target.toFixed(
        meta.decimals,
      )}`,
      higherBetter: meta.higherBetter,
      status,
      hint: L(lang, meta.hint, meta.hintEn),
      desc: meta.desc(display, lang),
    };
  });
}

/* ------------------------------------------------------------------ */
/* Calibration curve                                                   */
/* ------------------------------------------------------------------ */

interface RawBin {
  center: number;
  calibrated: number;
  raw: number;
  count: number;
}

const RAW_BINS: RawBin[] = [
  { center: 0.05, calibrated: 0.052, raw: 0.021, count: 4820 },
  { center: 0.15, calibrated: 0.141, raw: 0.088, count: 6120 },
  { center: 0.25, calibrated: 0.263, raw: 0.176, count: 7480 },
  { center: 0.35, calibrated: 0.338, raw: 0.281, count: 8210 },
  { center: 0.45, calibrated: 0.462, raw: 0.392, count: 7640 },
  { center: 0.55, calibrated: 0.541, raw: 0.508, count: 6350 },
  { center: 0.65, calibrated: 0.668, raw: 0.632, count: 4980 },
  { center: 0.75, calibrated: 0.742, raw: 0.786, count: 3720 },
  { center: 0.85, calibrated: 0.861, raw: 0.889, count: 2140 },
  { center: 0.95, calibrated: 0.938, raw: 0.972, count: 960 },
];

const RAW_TOTAL = RAW_BINS.reduce((sum, bin) => sum + bin.count, 0);

function buildCalibration(profile: VersionProfile): CalibrationCurve {
  const countScale = profile.datasetSize / RAW_TOTAL;

  const bins: CalibrationBin[] = RAW_BINS.map((bin, index) => ({
    label: `${(index / 10).toFixed(1)}–${((index + 1) / 10).toFixed(1)}`,
    center: bin.center,
    calibrated: Number(
      (bin.center + (bin.calibrated - bin.center) * profile.calibScale).toFixed(4),
    ),
    raw: bin.raw,
    count: Math.round(bin.count * countScale),
  }));

  const total = bins.reduce((sum, bin) => sum + bin.count, 0) || 1;
  const ece =
    bins.reduce(
      (sum, bin) =>
        sum + (bin.count / total) * Math.abs(bin.calibrated - bin.center),
      0,
    ) || 0;
  const rawEce =
    bins.reduce(
      (sum, bin) => sum + (bin.count / total) * Math.abs(bin.raw - bin.center),
      0,
    ) || 0;
  const mce = bins.reduce(
    (max, bin) => Math.max(max, Math.abs(bin.calibrated - bin.center)),
    0,
  );

  return {
    bins,
    ece: Number(ece.toFixed(4)),
    rawEce: Number(rawEce.toFixed(4)),
    mce: Number(mce.toFixed(4)),
    brier: profile.calibrationBrier,
    total,
  };
}

/* ------------------------------------------------------------------ */
/* Ablation study                                                      */
/* ------------------------------------------------------------------ */

interface AblationRaw {
  id: string;
  label: string;
  labelEn: string;
  featureCount: number;
  auc: number;
  ks: number;
  note: string;
  noteEn: string;
  /** 该特征组被引入的版本排位，用于按版本裁剪。 */
  since: number;
}

const ABLATION_REF_AUC = 0.874;
const ABLATION_REF_KS = 0.412;

const ABLATION_RAW: AblationRaw[] = [
  {
    id: "credit",
    label: "履约与信用记录",
    labelEn: "Performance & credit records",
    featureCount: 14,
    auc: 0.812,
    ks: 0.352,
    note: "核心特征组，剔除后区分度断崖式下降，是模型的第一驱动来源。",
    noteEn: "The core group; removing it causes a cliff-drop in discrimination, the model's primary driver.",
    since: 1,
  },
  {
    id: "capital",
    label: "资本结构与杠杆",
    labelEn: "Capital structure & leverage",
    featureCount: 11,
    auc: 0.829,
    ks: 0.368,
    note: "偿债能力与杠杆水平，承担主要的财务性区分贡献。",
    noteEn: "Solvency and leverage, carrying the main financial discrimination contribution.",
    since: 1,
  },
  {
    id: "compliance",
    label: "涉诉与合规表现",
    labelEn: "Judicial & compliance",
    featureCount: 9,
    auc: 0.838,
    ks: 0.379,
    note: "司法与合规负面信号，对尾部高风险样本的识别贡献显著。",
    noteEn: "Judicial and compliance negative signals, contributing significantly to identifying tail high-risk samples.",
    since: 2,
  },
  {
    id: "guarantee",
    label: "关联方与对外担保",
    labelEn: "Related-party guarantees",
    featureCount: 12,
    auc: 0.843,
    ks: 0.383,
    note: "关联担保放大风险传导，是图谱类特征的主要承载组。",
    noteEn: "Related guarantees amplify risk contagion; the main carrier of graph-based features.",
    since: 4,
  },
  {
    id: "capacity",
    label: "经营与订单能力",
    labelEn: "Operating & order capacity",
    featureCount: 8,
    auc: 0.851,
    ks: 0.389,
    note: "订单能见度与经营稳定性，对中期违约倾向有一定解释力。",
    noteEn: "Order visibility and operating stability, with some explanatory power over medium-term default propensity.",
    since: 1,
  },
  {
    id: "operation",
    label: "客户与供应链集中度",
    labelEn: "Customer & supply concentration",
    featureCount: 7,
    auc: 0.858,
    ks: 0.396,
    note: "集中度决定收入波动，剔除后对短周期风险识别略有削弱。",
    noteEn: "Concentration drives revenue volatility; removing it slightly weakens short-cycle risk detection.",
    since: 1,
  },
  {
    id: "governance",
    label: "治理与股权稳定性",
    labelEn: "Governance & equity stability",
    featureCount: 6,
    auc: 0.863,
    ks: 0.402,
    note: "控制权稳定性与股权结构，贡献中等偏小但具备稳定性。",
    noteEn: "Control stability and equity structure, a small-to-medium but stable contribution.",
    since: 1,
  },
  {
    id: "environment",
    label: "行业与国别环境",
    labelEn: "Industry & country environment",
    featureCount: 5,
    auc: 0.867,
    ks: 0.406,
    note: "行业景气与国别宏观，主要在跨国外推场景发挥作用。",
    noteEn: "Industry cycle and country macro, mainly effective in cross-country extrapolation.",
    since: 1,
  },
  {
    id: "scale",
    label: "企业规模与经营年限",
    labelEn: "Scale & years in operation",
    featureCount: 4,
    auc: 0.871,
    ks: 0.409,
    note: "规模与存续期溢价，单独贡献最小，但与其它组存在交互。",
    noteEn: "Scale and longevity premium, the smallest standalone contribution but interacting with other groups.",
    since: 1,
  },
];

function buildAblation(profile: VersionProfile, lang: Lang): AblationStudy {
  const baseAuc = profile.metrics.auc[1];
  const baseKs = profile.metrics.ks[1];
  const rank = VERSION_RANK[profile.version] ?? 4;
  const aucFactor = baseAuc / ABLATION_REF_AUC;
  const ksFactor = baseKs / ABLATION_REF_KS;

  const rawRows = ABLATION_RAW.filter((item) => item.since <= rank)
    .map((item) => {
      const auc = Number((item.auc * aucFactor).toFixed(3));
      const ks = Number((item.ks * ksFactor).toFixed(3));
      return {
        ...item,
        auc,
        ks,
        aucDrop: Number((baseAuc - auc).toFixed(3)),
        ksDrop: Number((baseKs - ks).toFixed(3)),
      };
    })
    .sort((a, b) => b.aucDrop - a.aucDrop);

  const maxDrop = rawRows[0]?.aucDrop || 1;

  const rows: AblationRow[] = rawRows.map((item) => ({
    id: item.id,
    label: L(lang, item.label, item.labelEn),
    featureCount: item.featureCount,
    auc: item.auc,
    ks: item.ks,
    aucDrop: item.aucDrop,
    ksDrop: item.ksDrop,
    importance: Math.max(1, Math.round((item.aucDrop / maxDrop) * 100)),
    note: L(lang, item.note, item.noteEn),
  }));

  return {
    baselineAuc: baseAuc,
    baselineKs: baseKs,
    rows,
  };
}

/* ------------------------------------------------------------------ */
/* Cross-country extrapolation decay                                   */
/* ------------------------------------------------------------------ */

interface ExtrapolationRaw {
  id: string;
  region: string;
  regionEn: string;
  short: string;
  shortEn: string;
  cohort: ExtrapolationCohort;
  sampleSize: number;
  auc: number;
  ks: number;
  psi: number;
}

const EXTRAPOLATION_REF_AUC = 0.874;
const EXTRAPOLATION_REF_KS = 0.412;

const EXTRAPOLATION_RAW: ExtrapolationRaw[] = [
  {
    id: "cn",
    region: "中国大陆",
    regionEn: "Chinese Mainland",
    short: "中国大陆",
    shortEn: "Chinese Mainland",
    cohort: "in",
    sampleSize: 48200,
    auc: 0.874,
    ks: 0.412,
    psi: 0.02,
  },
  {
    id: "hksg",
    region: "香港 / 新加坡",
    regionEn: "Hong Kong / Singapore",
    short: "香港 / 新加坡",
    shortEn: "HK / SG",
    cohort: "near",
    sampleSize: 12400,
    auc: 0.868,
    ks: 0.405,
    psi: 0.06,
  },
  {
    id: "jpkr",
    region: "日本 / 韩国",
    regionEn: "Japan / Korea",
    short: "日本 / 韩国",
    shortEn: "JP / KR",
    cohort: "near",
    sampleSize: 9600,
    auc: 0.859,
    ks: 0.394,
    psi: 0.09,
  },
  {
    id: "vnin",
    region: "越南 / 印度",
    regionEn: "Vietnam / India",
    short: "越南 / 印度",
    shortEn: "VN / IN",
    cohort: "far",
    sampleSize: 6800,
    auc: 0.845,
    ks: 0.373,
    psi: 0.15,
  },
  {
    id: "mxbr",
    region: "墨西哥 / 巴西",
    regionEn: "Mexico / Brazil",
    short: "墨西哥 / 巴西",
    shortEn: "MX / BR",
    cohort: "far",
    sampleSize: 4200,
    auc: 0.832,
    ks: 0.358,
    psi: 0.21,
  },
  {
    id: "rtr",
    region: "俄罗斯 / 土耳其",
    regionEn: "Russia / Turkey",
    short: "俄罗斯 / 土耳其",
    shortEn: "RU / TR",
    cohort: "far",
    sampleSize: 3100,
    auc: 0.814,
    ks: 0.336,
    psi: 0.29,
  },
];

const COHORT_LABEL: Record<Lang, Record<ExtrapolationCohort, string>> = {
  zh: {
    in: "境内基准",
    near: "近域外推",
    far: "远域外推",
  },
  en: {
    in: "Domestic baseline",
    near: "Near-domain extrapolation",
    far: "Far-domain extrapolation",
  },
};

/** 分组名称（按语言）。 */
export function cohortLabel(lang: Lang): Record<ExtrapolationCohort, string> {
  return COHORT_LABEL[lang];
}

function decisionFor(row: ExtrapolationRaw, lang: Lang): string {
  if (row.cohort === "in") return L(lang, "直接适用", "Directly applicable");
  if (row.psi <= 0.1 && row.auc >= 0.855)
    return L(lang, "正常适用", "Applicable");
  if (row.psi <= 0.15) return L(lang, "需本地校准", "Local calibration needed");
  return L(lang, "建议本地重训", "Local retraining advised");
}

function buildExtrapolation(
  profile: VersionProfile,
  lang: Lang,
): ExtrapolationStudy {
  const baseAuc = profile.metrics.auc[1];
  const baseKs = profile.metrics.ks[1];
  const aucFactor = baseAuc / EXTRAPOLATION_REF_AUC;
  const ksFactor = baseKs / EXTRAPOLATION_REF_KS;

  const rows: ExtrapolationRow[] = EXTRAPOLATION_RAW.map((item) => {
    const auc = Number((item.auc * aucFactor).toFixed(3));
    const ks = Number((item.ks * ksFactor).toFixed(3));
    return {
      id: item.id,
      region: L(lang, item.region, item.regionEn),
      short: L(lang, item.short, item.shortEn),
      cohort: item.cohort,
      sampleSize: item.sampleSize,
      auc,
      ks,
      aucDecay: Number((auc - baseAuc).toFixed(3)),
      ksDecay: Number((ks - baseKs).toFixed(3)),
      psi: item.psi,
      decision: decisionFor(item, lang),
    };
  });

  return {
    baselineAuc: baseAuc,
    baselineKs: baseKs,
    rows,
  };
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                           */
/* ------------------------------------------------------------------ */

export function buildEvalDashboard(
  version: string = EVAL_MODEL_VERSION,
  lang: Lang = "zh",
): EvalDashboard {
  const profile = resolveProfile(version);

  return {
    modelVersion: profile.version,
    validatedAt: profile.validatedAt,
    trainedAt: profile.trainedAt,
    datasetSize: profile.datasetSize,
    featureCount: profile.featureCount,
    positiveRate: profile.positiveRate,
    splitRatio: L(lang, "训练 70% · 验证 15% · 测试 15%", "Train 70% · Valid 15% · Test 15%"),
    metrics: buildMetrics(profile, lang),
    calibration: buildCalibration(profile),
    ablation: buildAblation(profile, lang),
    extrapolation: buildExtrapolation(profile, lang),
  };
}

/* ------------------------------------------------------------------ */
/* Reproduce runs                                                      */
/* ------------------------------------------------------------------ */

const SNAPSHOT = "snap-4.2.0-demo";
const ENGINE = "demo-simulator@1.0";

function seedFrom(text: string): string {
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  }
  return hash.toString(16).toUpperCase().padStart(8, "0");
}

interface TargetDescriptor {
  code: string;
  title: string;
  subtitle: string;
  focusLabel: string;
  focusValue: string;
  focusNote: string;
  metricLabel: string;
}

function describeTarget(
  dashboard: EvalDashboard,
  key: string,
  lang: Lang,
): TargetDescriptor {
  if (key === "all") {
    return {
      code: "ALL",
      title: L(lang, "复现全部指标", "Reproduce all metrics"),
      subtitle: L(
        lang,
        "回放四项主指标、校准曲线、消融实验与跨国外推衰减的演示快照",
        "Replay demo snapshots of the four main metrics, calibration curve, ablation and cross-country extrapolation decay",
      ),
      focusLabel: L(lang, "复现结论", "Result"),
      focusValue: L(lang, "演示指标已展示", "Demo metrics displayed"),
      focusNote: L(
        lang,
        "展示预设快照，未执行真实模型计算或验证",
        "Preset snapshots are shown; no live model computation or validation ran",
      ),
      metricLabel: L(lang, "全部指标", "All metrics"),
    };
  }

  const metric = dashboard.metrics.find((item) => item.key === key);
  if (metric) {
    return {
      code: metric.key.toUpperCase(),
      title: L(
        lang,
        `复现「${metric.label}」指标`,
        `Reproduce the “${metric.label}” metric`,
      ),
      subtitle: L(
        lang,
        `${metric.fullLabel} · 从只读快照重放完整评估链路`,
        `${metric.fullLabel} · Replaying the full evaluation pipeline from the read-only snapshot`,
      ),
      focusLabel: L(
        lang,
        `复现 ${metric.label}`,
        `Reproduced ${metric.label}`,
      ),
      focusValue: metric.display,
      focusNote: L(
        lang,
        `登记基线 ${metric.display} · 偏差 0.0000 · 结论一致`,
        `Registered baseline ${metric.display} · deviation 0.0000 · consistent`,
      ),
      metricLabel: metric.label,
    };
  }

  if (key === "calibration") {
    return {
      code: "CAL",
      title: L(lang, "复现校准曲线", "Reproduce the calibration curve"),
      subtitle: L(
        lang,
        "重算分箱观测违约率与期望校准误差（ECE）",
        "Recompute binned observed default rates and the expected calibration error (ECE)",
      ),
      focusLabel: L(lang, "复现 ECE", "Reproduced ECE"),
      focusValue: dashboard.calibration.ece.toFixed(4),
      focusNote: L(
        lang,
        `校准前 ECE ${dashboard.calibration.rawEce.toFixed(4)} · 分箱数 ${dashboard.calibration.bins.length}`,
        `Pre-calibration ECE ${dashboard.calibration.rawEce.toFixed(4)} · bins ${dashboard.calibration.bins.length}`,
      ),
      metricLabel: L(lang, "校准曲线", "Calibration curve"),
    };
  }

  if (key === "ablation") {
    const top = dashboard.ablation.rows[0];
    return {
      code: "ABL",
      title: L(lang, "复现消融实验", "Reproduce the ablation study"),
      subtitle: L(
        lang,
        `逐组剔除 ${dashboard.ablation.rows.length} 个特征组并重新评估`,
        `Remove each of the ${dashboard.ablation.rows.length} feature groups in turn and re-evaluate`,
      ),
      focusLabel: L(lang, "复现结论", "Result"),
      focusValue: L(
        lang,
        `${dashboard.ablation.rows.length} 组消融一致`,
        `${dashboard.ablation.rows.length} ablation groups consistent`,
      ),
      focusNote: L(
        lang,
        `基准 AUC ${dashboard.ablation.baselineAuc.toFixed(3)} · 最大贡献组「${top?.label ?? "—"}」`,
        `Baseline AUC ${dashboard.ablation.baselineAuc.toFixed(3)} · top contributing group “${top?.label ?? "—"}”`,
      ),
      metricLabel: L(lang, "消融实验", "Ablation study"),
    };
  }

  const decays = dashboard.extrapolation.rows.map((row) => row.aucDecay);
  const psis = dashboard.extrapolation.rows.map((row) => row.psi);
  return {
    code: "EXT",
    title: L(lang, "复现跨国外推衰减", "Reproduce cross-country extrapolation decay"),
    subtitle: L(
      lang,
      `按 ${dashboard.extrapolation.rows.length} 个国别分组重算 AUC / KS 与 PSI`,
      `Recompute AUC / KS and PSI across ${dashboard.extrapolation.rows.length} country cohorts`,
    ),
    focusLabel: L(lang, "复现结论", "Result"),
    focusValue: L(
      lang,
      `${dashboard.extrapolation.rows.length} 组外推曲线一致`,
      `${dashboard.extrapolation.rows.length} extrapolation curves consistent`,
    ),
    focusNote: L(
      lang,
      `最大 AUC 衰减 ${Math.min(...decays).toFixed(3)} · 最差组 PSI ${Math.max(
        ...psis,
      ).toFixed(2)}`,
      `Max AUC decay ${Math.min(...decays).toFixed(3)} · worst-cohort PSI ${Math.max(
        ...psis,
      ).toFixed(2)}`,
    ),
    metricLabel: L(lang, "跨国外推衰减", "Cross-country extrapolation decay"),
  };
}

const STEP_DURATIONS = [460, 620, 880, 700, 420];

export function buildReproduceRun(
  dashboard: EvalDashboard,
  key: string,
  lang: Lang = "zh",
): ReproduceRun {
  const descriptor = describeTarget(dashboard, key, lang);
  const seed = "20240621";
  const runId = `RUN-${descriptor.code}-${seedFrom(`${key}:${dashboard.modelVersion}`).slice(0, 6)}`;
  const seedNum = parseInt(seedFrom(`${key}:${dashboard.modelVersion}`).slice(0, 6), 16);
  const mm = String(seedNum % 60).padStart(2, "0");
  const ss = String((seedNum >> 6) % 60).padStart(2, "0");

  const steps: ReproduceStep[] = [
    {
      label: L(lang, "锁定数据快照", "Lock the data snapshot"),
      detail: L(
        lang,
        `挂载只读快照 ${SNAPSHOT}，冻结全部输入以避免数据漂移`,
        `Mount read-only snapshot ${SNAPSHOT} and freeze all inputs to avoid data drift`,
      ),
      durationMs: STEP_DURATIONS[0],
    },
    {
      label: L(lang, "重建验证样本", "Rebuild validation samples"),
      detail: L(
        lang,
        `重放切分逻辑 · seed=${seed} · n=${dashboard.datasetSize.toLocaleString("en-US")}`,
        `Replay split logic · seed=${seed} · n=${dashboard.datasetSize.toLocaleString("en-US")}`,
      ),
      durationMs: STEP_DURATIONS[1],
    },
    {
      label: L(lang, "模型推理", "Model inference"),
      detail: L(
        lang,
        `加载 ${ENGINE} · 256 棵树 · ${dashboard.featureCount} 维特征`,
        `Load ${ENGINE} · 256 trees · ${dashboard.featureCount} features`,
      ),
      durationMs: STEP_DURATIONS[2],
    },
    {
      label: L(lang, "指标计算", "Metric computation"),
      detail: L(
        lang,
        `计算 ${descriptor.metricLabel} 及 1000 次自助法置信区间`,
        `Compute ${descriptor.metricLabel} and 1000-round bootstrap confidence intervals`,
      ),
      durationMs: STEP_DURATIONS[3],
    },
    {
      label: L(lang, "结果校验", "Result verification"),
      detail: L(
        lang,
        "与登记基线逐项比对，并将复现记录写入验证台账",
        "Compare item by item against the registered baseline and write the record to the validation log",
      ),
      durationMs: STEP_DURATIONS[4],
    },
  ];

  const totalMs = steps.reduce((sum, step) => sum + step.durationMs, 0);

  const logs = [
    `[snap] mount ${SNAPSHOT} (readonly) · checksum ok`,
    `[data] split replayed · seed=${seed} · n=${dashboard.datasetSize.toLocaleString("en-US")}`,
    `[model] loaded ${ENGINE} · trees=256 · features=${dashboard.featureCount}`,
    `[metric] target=${descriptor.code} · batch=4096 · bootstrap=1000`,
    `[verify] reproduced matches registry · delta=0.0000`,
  ];

  return {
    target: key,
    title: descriptor.title,
    subtitle: descriptor.subtitle,
    runId,
    seed,
    snapshot: SNAPSHOT,
    sampleSize: dashboard.datasetSize,
    engine: ENGINE,
    startedAt: `2026-09-24 10:${mm}:${ss}`,
    duration: `${(totalMs / 1000).toFixed(2)} s`,
    focusLabel: descriptor.focusLabel,
    focusValue: descriptor.focusValue,
    focusNote: descriptor.focusNote,
    steps,
    logs,
  };
}
