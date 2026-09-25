import { companies } from "@/features/demo-scenarios/model/fixtures/companies";
import { buildScoreDetail, formatContribution } from "@/features/demo-scenarios/lib/score";
import {
  applyRiskTransmission,
  buildGraphData,
  riskLabel,
  riskLabelEn,
} from "@/features/demo-scenarios/lib/graph";
import type {
  Company,
  CompanyProfile,
  Evidence,
  EvidenceType,
  ReportDoc,
  ReportParagraph,
  ReportSection,
  ReportSentence,
  RiskLevel,
} from "@/entities/demo/model/types";

export type Lang = "zh" | "en";

const L = (lang: Lang, zh: string, en: string): string =>
  lang === "en" ? en : zh;

const RISK_ORDER: Record<RiskLevel, number> = { high: 0, medium: 1, low: 2 };

interface Registry {
  evidence: Evidence[];
  numberById: Map<string, number>;
}

function cite(
  registry: Registry,
  id: string,
  ev: Omit<Evidence, "id" | "number">,
): number {
  const existing = registry.numberById.get(id);
  if (existing) return existing;
  const number = registry.evidence.length + 1;
  registry.numberById.set(id, number);
  registry.evidence.push({ id, number, ...ev });
  return number;
}

function para(id: string, sentences: ReportSentence[]): ReportParagraph {
  return { id, sentences };
}

function sentence(
  id: string,
  text: string,
  citations: number[] = [],
): ReportSentence {
  return { id, text, citations };
}

function countWords(sections: ReportSection[]): number {
  return sections.reduce(
    (sum, section) =>
      sum +
      section.paragraphs.reduce(
        (pSum, p) =>
          pSum +
          p.sentences.reduce(
            (sSum, s) => sSum + s.text.replace(/\s/g, "").length,
            0,
          ),
        0,
      ),
    0,
  );
}

function countSentences(sections: ReportSection[]): number {
  return sections.reduce(
    (sum, section) =>
      sum + section.paragraphs.reduce((pSum, p) => pSum + p.sentences.length, 0),
    0,
  );
}

/**
 * Builds a deterministic credit-report document for a company.
 * Sentences carry citation numbers that map to the evidence registry, so the
 * same company (+ language) always produces the same report and evidence cards.
 */
export function buildReport(
  company: Company,
  profile: CompanyProfile,
  detail: ReturnType<typeof buildScoreDetail>,
  lang: Lang = "zh",
): ReportDoc {
  const registry: Registry = { evidence: [], numberById: new Map() };
  const { facts } = profile;
  const factsEn = profile.factsEn;
  const isEn = lang === "en";

  const name = isEn ? company.nameEn : company.nameCn;
  const country = isEn ? (company.countryEn ?? company.country) : company.country;
  const industry = isEn ? (company.industryEn ?? company.industry) : company.industry;

  const fRegisteredCapital = isEn ? (factsEn?.registeredCapital ?? facts.registeredCapital) : facts.registeredCapital;
  const fPaidInCapital = isEn ? (factsEn?.paidInCapital ?? facts.paidInCapital) : facts.paidInCapital;
  const fLegalPerson = isEn ? (factsEn?.legalPerson ?? facts.legalPerson) : facts.legalPerson;
  const fActualController = isEn ? (factsEn?.actualController ?? facts.actualController) : facts.actualController;
  const fControllerStake = isEn ? (factsEn?.controllerStake ?? facts.controllerStake) : facts.controllerStake;
  const fEmployees = isEn ? (factsEn?.employees ?? facts.employees) : facts.employees;
  const fListed = isEn ? (factsEn?.listed ?? facts.listed) : facts.listed;
  const fRatingAgency = isEn ? (factsEn?.ratingAgency ?? facts.ratingAgency) : facts.ratingAgency;
  const fMainBanks = isEn ? (factsEn?.mainBanks ?? facts.mainBanks) : facts.mainBanks;
  const fSettlement = isEn ? (factsEn?.settlement ?? facts.settlement) : facts.settlement;
  const riskText = L(lang, riskLabel[company.riskLevel], riskLabelEn[company.riskLevel]);

  const LEVEL_LABEL: Record<RiskLevel, string> = {
    high: L(lang, "高风险", "high risk"),
    medium: L(lang, "中风险", "medium risk"),
    low: L(lang, "低风险", "low risk"),
  };

  const flagText = (flag: CompanyProfile["riskFlags"][number]) => ({
    label: isEn ? (flag.labelEn ?? flag.label) : flag.label,
    category: isEn ? (flag.categoryEn ?? flag.category) : flag.category,
    desc: isEn ? (flag.descEn ?? flag.desc) : flag.desc,
  });
  const dimName = (d: CompanyProfile["fiveC"][number]) =>
    isEn ? d.en : `${d.label}（${d.en}）`;
  const dimNote = (d: CompanyProfile["fiveC"][number]) =>
    isEn ? (d.noteEn ?? d.note) : d.note;

  // --- derived inputs -------------------------------------------------------
  const flags = [...profile.riskFlags].sort(
    (a, b) => RISK_ORDER[a.level] - RISK_ORDER[b.level],
  );
  const highCount = flags.filter((f) => f.level === "high").length;
  const midCount = flags.filter((f) => f.level === "medium").length;
  const lowCount = flags.filter((f) => f.level === "low").length;
  const complianceFlag = profile.riskFlags.find(
    (f) => f.category === "合规表现",
  );

  const dimensions = [...profile.fiveC].sort((a, b) => a.score - b.score);
  const weakDim = dimensions[0];
  const strongDim = dimensions[dimensions.length - 1];

  const features = detail.features;
  const topPos = features.find((f) => f.contribution > 0);
  const negativeFeatures = [...features]
    .filter((f) => f.contribution < 0)
    .sort((a, b) => a.contribution - b.contribution);
  const topNeg = negativeFeatures[0];
  const secondNeg = negativeFeatures[1];

  const benchSector = detail.benchmarks.find((b) => b.key === "sector");
  const benchSize = detail.benchmarks.find((b) => b.key === "size");
  const benchAll =
    detail.benchmarks.find((b) => b.key === "all") ??
    detail.benchmarks[detail.benchmarks.length - 1];

  const graph = buildGraphData(companies, company, profile, lang);
  const paths = applyRiskTransmission(graph);
  const relatedCount = graph.nodes.filter((n) => n.hop > 0).length;
  const highPaths = paths.filter((p) => p.riskLevel === "high");
  const topPath = paths[0];

  const guarantors = profile.relatedParties.filter(
    (p) => /担保/.test(p.relation) || /担保/.test(p.exposure),
  );
  const latestNegative = [...profile.timeline]
    .filter((t) => t.impact === "negative")
    .sort((a, b) => (a.date < b.date ? 1 : -1))[0];

  const pdDesc =
    company.defaultProb > detail.pdBase
      ? L(
          lang,
          `较模型基准 ${detail.pdBase}% 高出 ${Math.abs(detail.pdDelta).toFixed(1)} 个百分点，违约风险高于全库中枢`,
          `${Math.abs(detail.pdDelta).toFixed(1)} pct above the ${detail.pdBase}% model base, higher than the library center`,
        )
      : L(
          lang,
          `较模型基准 ${detail.pdBase}% 低 ${Math.abs(detail.pdDelta).toFixed(1)} 个百分点，违约风险低于全库中枢`,
          `${Math.abs(detail.pdDelta).toFixed(1)} pct below the ${detail.pdBase}% model base, lower than the library center`,
        );

  const conclusionByRisk: Record<RiskLevel, string> = {
    low: L(
      lang,
      "总体判断，该主体信用资质良好、履约记录稳定，可作为常规授信对象纳入合作白名单。",
      "Overall, the entity has sound credit quality and stable performance, and can be included as a standard credit counterparty.",
    ),
    medium: L(
      lang,
      "总体判断，该主体信用资质中性偏弱，建议在增信与账期约束到位的前提下审慎开展合作。",
      "Overall, the entity's credit quality is neutral to weak; proceed cautiously once credit enhancement and tenor constraints are in place.",
    ),
    high: L(
      lang,
      "总体判断，该主体信用资质较差、风险信号集中，建议审慎介入，避免形成裸露风险敞口。",
      "Overall, the entity has weak credit quality and concentrated risk signals; intervene cautiously to avoid naked exposure.",
    ),
  };

  const mitigationByRisk: Record<RiskLevel, string> = {
    low: L(
      lang,
      "建议维持季度贷后监控频率，授信额度与账期按标准条件执行，并持续跟踪其大客户集中度变化。",
      "Maintain quarterly post-loan monitoring, execute the limit and tenor on standard terms, and keep tracking its customer-concentration changes.",
    ),
    medium: L(
      lang,
      "建议追加实际控制人连带责任保证，将账期压缩至 60 天以内，并按月监控应收账龄与关联方担保变动。",
      "Add a joint-liability guarantee from the actual controller, compress the tenor to within 60 days, and monitor receivable aging and related-party guarantee changes monthly.",
    ),
    high: L(
      lang,
      "建议暂停新增信用敞口，存量业务逐步压退；如确需合作须采用预付款、信用证或足额抵押等风险可控方式。",
      "Suspend new credit exposure and wind down existing business; if cooperation is needed, use prepayment, letter of credit or full collateral.",
    ),
  };

  // --- evidence registry (numbered in reading order) ------------------------
  const regNo = cite(registry, "fact-register", {
    type: "fact",
    title: L(lang, "工商登记信息", "Business registration"),
    snippet: `${company.regNo} · ${country} · ${industry}`,
    source: L(lang, "全国企业信用信息公示系统", "National enterprise credit disclosure system"),
    metric: company.sector,
    confidence: 99,
    capturedAt: company.updatedAt,
    refPath: `/company/${company.id}`,
    refLabel: L(lang, "查看工商信息卡", "View registration card"),
  });

  const capNo = cite(registry, "fact-capital", {
    type: "fact",
    title: L(lang, "注册资本与实缴", "Registered & paid-in capital"),
    snippet: `${fRegisteredCapital} · ${L(lang, "实缴", "paid-in")} ${fPaidInCapital}`,
    source: L(lang, "工商登记 / 验资信息", "Registry / capital verification"),
    metric: fRegisteredCapital,
    confidence: 96,
    capturedAt: company.updatedAt,
    refPath: `/company/${company.id}`,
    refLabel: L(lang, "查看工商信息卡", "View registration card"),
  });

  const scaleNo = cite(registry, "fact-scale", {
    type: "fact",
    title: L(lang, "规模与存续", "Scale & vintage"),
    snippet: L(
      lang,
      `成立于 ${facts.established} · 员工 ${fEmployees} · ${fListed}`,
      `Founded ${facts.established} · ${fEmployees} staff · ${fListed}`,
    ),
    source: L(lang, "工商登记 / 年报披露", "Registry / annual report"),
    metric: fEmployees,
    confidence: 94,
    capturedAt: company.updatedAt,
    refPath: `/company/${company.id}`,
    refLabel: L(lang, "查看工商信息卡", "View registration card"),
  });

  const controlNo = cite(registry, "fact-control", {
    type: "fact",
    title: L(lang, "股权与控制权", "Ownership & control"),
    snippet: L(
      lang,
      `实际控制人 ${fActualController} · ${fControllerStake} · 法定代表人 ${fLegalPerson}`,
      `Actual controller ${fActualController} · ${fControllerStake} · legal representative ${fLegalPerson}`,
    ),
    source: L(lang, "工商登记 / 穿透股权", "Registry / equity look-through"),
    metric: fControllerStake,
    confidence: 95,
    capturedAt: company.updatedAt,
    refPath: `/company/${company.id}`,
    refLabel: L(lang, "查看治理结构", "View governance"),
  });

  const ratingNo = cite(registry, "fact-rating", {
    type: "fact",
    title: L(lang, "外部评级与往来银行", "External rating & banks"),
    snippet: L(
      lang,
      `${fRatingAgency} · 主力银行 ${fMainBanks}`,
      `${fRatingAgency} · main banks ${fMainBanks}`,
    ),
    source: L(lang, "评级机构 / 银行流水", "Rating agencies / bank statements"),
    metric: fRatingAgency,
    confidence: 90,
    capturedAt: company.updatedAt,
    refPath: `/company/${company.id}`,
    refLabel: L(lang, "查看外部评级", "View external rating"),
  });

  const bankNo = cite(registry, "fact-settlement", {
    type: "fact",
    title: L(lang, "结算方式", "Settlement terms"),
    snippet: `${fSettlement} · ${L(lang, facts.revenue, isEn ? (factsEn?.revenue ?? facts.revenue) : facts.revenue)}`,
    source: L(lang, "银行流水 / 合同台账", "Bank statements / contracts"),
    metric: fSettlement,
    confidence: 88,
    capturedAt: company.updatedAt,
    refPath: `/company/${company.id}`,
    refLabel: L(lang, "查看结算信息", "View settlement"),
  });

  const scoreNo = cite(registry, "snapshot-score", {
    type: "snapshot",
    title: L(lang, "信用评分快照", "Credit score snapshot"),
    snippet: L(
      lang,
      `信用分 ${company.creditScore} · ${detail.grade} 级 · 违约概率 ${company.defaultProb}% · 风险分位 P${detail.riskPercentile}`,
      `Score ${company.creditScore} · grade ${detail.grade} · default prob ${company.defaultProb}% · risk percentile P${detail.riskPercentile}`,
    ),
    source: L(lang, `信用评估模型 ${detail.modelVersion}`, `Credit model ${detail.modelVersion}`),
    metric: `${company.creditScore} ${L(lang, "分", "pts")}`,
    confidence: detail.confidence,
    capturedAt: detail.evaluatedAt,
    refPath: `/score/${company.id}`,
    refLabel: L(lang, "查看评分详情", "View score details"),
  });

  const limitNo = cite(registry, "snapshot-limit", {
    type: "snapshot",
    title: L(lang, "授信额度参考", "Reference credit limit"),
    snippet: L(
      lang,
      `参考授信额度 ${company.creditLimit} · 风险等级${riskText}`,
      `Reference limit ${company.creditLimit} · risk level ${riskText}`,
    ),
    source: L(lang, "授信决策引擎", "Underwriting engine"),
    metric: company.creditLimit,
    confidence: detail.confidence,
    capturedAt: detail.evaluatedAt,
    refPath: `/decision/${company.id}`,
    refLabel: L(lang, "查看决策单", "View decision"),
  });

  const modelNo = cite(registry, "snapshot-model", {
    type: "snapshot",
    title: L(lang, "归因口径", "Attribution method"),
    snippet: L(
      lang,
      `基准值 ${detail.baseValue} 分 · ${detail.features.length} 项特征 · 提分 ${detail.positiveCount} / 扣分 ${detail.negativeCount}`,
      `Base ${detail.baseValue} · ${detail.features.length} features · ${detail.positiveCount} up / ${detail.negativeCount} down`,
    ),
    source: L(
      lang,
      `SHAP 加性归因 · 模型 ${detail.modelVersion}`,
      `SHAP additive attribution · model ${detail.modelVersion}`,
    ),
    metric: L(lang, `${detail.features.length} 项因子`, `${detail.features.length} factors`),
    confidence: detail.confidence,
    capturedAt: detail.evaluatedAt,
    refPath: `/score/${company.id}`,
    refLabel: L(lang, "查看瀑布图", "View waterfall"),
  });

  const flagSummaryNo = cite(registry, "flag-summary", {
    type: "flag",
    title: L(lang, "风险信号扫描", "Risk signal scan"),
    snippet: L(
      lang,
      `命中 ${flags.length} 项风险信号：高风险 ${highCount} · 中风险 ${midCount} · 低风险 ${lowCount}`,
      `${flags.length} risk signals hit: ${highCount} high · ${midCount} medium · ${lowCount} low`,
    ),
    source: L(
      lang,
      "多源风险扫描引擎（司法 / 票据 / 舆情 / 财务）",
      "Multi-source risk engine (judicial / note / sentiment / financial)",
    ),
    metric: L(lang, `${flags.length} 项`, `${flags.length} items`),
    confidence: 91,
    capturedAt: company.updatedAt,
    refPath: `/company/${company.id}`,
    refLabel: L(lang, "查看风险标签", "View risk flags"),
  });

  const flagNoById = new Map<string, number>();
  flags.slice(0, 4).forEach((flag) => {
    const ft = flagText(flag);
    const no = cite(registry, `flag-${flag.id}`, {
      type: "flag",
      title: ft.label,
      snippet: ft.desc,
      source: flag.source,
      metric: LEVEL_LABEL[flag.level],
      confidence: flag.level === "high" ? 93 : 86,
      capturedAt: flag.detectedAt,
      refPath: `/company/${company.id}`,
      refLabel: L(lang, "查看风险标签", "View risk flags"),
    });
    flagNoById.set(flag.id, no);
  });

  const weakDimNo = cite(registry, `fivec-${weakDim.key}`, {
    type: "feature",
    title: `5C · ${dimName(weakDim)}`,
    snippet: L(
      lang,
      `得分 ${weakDim.score}/100 · 权重 ${weakDim.weight}% · ${dimNote(weakDim)}`,
      `Score ${weakDim.score}/100 · weight ${weakDim.weight}% · ${dimNote(weakDim)}`,
    ),
    source: L(lang, "5C 维度评估", "5C dimension assessment"),
    metric: `${weakDim.score} ${L(lang, "分", "pts")}`,
    confidence: 89,
    capturedAt: company.updatedAt,
    refPath: `/company/${company.id}`,
    refLabel: L(lang, "查看 5C 评估", "View 5C assessment"),
  });

  const strongDimNo = cite(registry, `fivec-${strongDim.key}`, {
    type: "feature",
    title: `5C · ${dimName(strongDim)}`,
    snippet: L(
      lang,
      `得分 ${strongDim.score}/100 · 权重 ${strongDim.weight}% · ${dimNote(strongDim)}`,
      `Score ${strongDim.score}/100 · weight ${strongDim.weight}% · ${dimNote(strongDim)}`,
    ),
    source: L(lang, "5C 维度评估", "5C dimension assessment"),
    metric: `${strongDim.score} ${L(lang, "分", "pts")}`,
    confidence: 89,
    capturedAt: company.updatedAt,
    refPath: `/company/${company.id}`,
    refLabel: L(lang, "查看 5C 评估", "View 5C assessment"),
  });

  const featureNoById = new Map<string, number>();
  const registerFeature = (featureId: string) => {
    const feature = features.find((f) => f.id === featureId);
    if (!feature) return undefined;
    const no = cite(registry, `feature-${feature.id}`, {
      type: "feature",
      title: feature.label,
      snippet: L(
        lang,
        `${feature.desc}特征取值：${feature.value}`,
        `${feature.desc} Feature value: ${feature.value}`,
      ),
      source: L(lang, `SHAP 归因 · ${feature.category}`, `SHAP attribution · ${feature.category}`),
      metric: formatContribution(feature.contribution),
      confidence: 92,
      capturedAt: detail.evaluatedAt,
      refPath: `/score/${company.id}`,
      refLabel: L(lang, "查看因子贡献", "View factor contribution"),
    });
    featureNoById.set(feature.id, no);
    return no;
  };

  const posFeatureNo = topPos ? registerFeature(topPos.id) : undefined;
  const negFeatureNo = topNeg ? registerFeature(topNeg.id) : undefined;
  const neg2FeatureNo = secondNeg ? registerFeature(secondNeg.id) : undefined;

  const benchSectorNo = benchSector
    ? cite(registry, "bench-sector", {
        type: "benchmark",
        title: L(lang, `行业基准 · ${benchSector.tag}`, `Sector benchmark · ${benchSector.tag}`),
        snippet: L(
          lang,
          `样本 ${benchSector.sampleSize} 家 · 均值 ${benchSector.avgScore} 分 · 均值违约率 ${benchSector.avgDefaultProb}%`,
          `${benchSector.sampleSize} firms · avg ${benchSector.avgScore} · avg default rate ${benchSector.avgDefaultProb}%`,
        ),
        source: L(lang, "社区基准库", "Community benchmark library"),
        metric: `${benchSector.diff >= 0 ? "+" : ""}${benchSector.diff} ${L(lang, "分", "pts")}`,
        confidence: 87,
        capturedAt: detail.evaluatedAt,
        refPath: `/score/${company.id}`,
        refLabel: L(lang, "查看社区对比", "View community comparison"),
      })
    : undefined;

  const benchSizeNo = benchSize
    ? cite(registry, "bench-size", {
        type: "benchmark",
        title: L(lang, `规模基准 · ${benchSize.tag}`, `Size benchmark · ${benchSize.tag}`),
        snippet: L(
          lang,
          `样本 ${benchSize.sampleSize} 家 · 均值 ${benchSize.avgScore} 分 · P${benchSize.percentile}`,
          `${benchSize.sampleSize} firms · avg ${benchSize.avgScore} · P${benchSize.percentile}`,
        ),
        source: L(lang, "社区基准库", "Community benchmark library"),
        metric: `P${benchSize.percentile}`,
        confidence: 87,
        capturedAt: detail.evaluatedAt,
        refPath: `/score/${company.id}`,
        refLabel: L(lang, "查看社区对比", "View community comparison"),
      })
    : undefined;

  const benchAllNo = cite(registry, "bench-all", {
    type: "benchmark",
    title: L(lang, `全库基准 · ${benchAll.tag}`, `Library benchmark · ${benchAll.tag}`),
    snippet: L(
      lang,
      `样本 ${benchAll.sampleSize} 家 · 均值 ${benchAll.avgScore} 分 · 全库分位 P${benchAll.percentile}`,
      `${benchAll.sampleSize} firms · avg ${benchAll.avgScore} · library percentile P${benchAll.percentile}`,
    ),
    source: L(lang, "社区基准库", "Community benchmark library"),
    metric: `P${benchAll.percentile}`,
    confidence: 90,
    capturedAt: detail.evaluatedAt,
    refPath: `/score/${company.id}`,
    refLabel: L(lang, "查看社区对比", "View community comparison"),
  });

  const graphOverviewNo = cite(registry, "graph-overview", {
    type: "graph",
    title: L(lang, "关联网络穿透", "Relation network look-through"),
    snippet: L(
      lang,
      `以评估主体为中心，共 ${relatedCount} 个关联主体、${graph.edges.length} 条关系边`,
      `${relatedCount} related entities and ${graph.edges.length} relation edges around the entity`,
    ),
    source: L(lang, "图谱关系库 · 2–3 跳穿透", "Graph library · 2–3 hop look-through"),
    metric: L(lang, `${relatedCount} 个关联方`, `${relatedCount} related parties`),
    confidence: 88,
    capturedAt: company.updatedAt,
    refPath: `/graph?company=${company.id}`,
    refLabel: L(lang, "查看图谱关系", "View graph relations"),
  });

  const pathNoById = new Map<string, number>();
  highPaths.slice(0, 3).forEach((path) => {
    const no = cite(registry, `graph-path-${path.nodeId}`, {
      type: "graph",
      title: L(lang, `风险传导路径 · ${path.label}`, `Risk transmission path · ${path.label}`),
      snippet: path.chain.join(" → "),
      source: L(lang, "图谱关系库 · 风险传导", "Graph library · risk transmission"),
      metric: L(lang, `${path.hops} 跳`, `${path.hops} hops`),
      confidence: 85,
      capturedAt: company.updatedAt,
      refPath: `/graph?company=${company.id}`,
      refLabel: L(lang, "定位该路径", "Locate the path"),
    });
    pathNoById.set(path.nodeId, no);
  });

  const guarantorNos = guarantors.slice(0, 3).map((party) => {
    const partyName = isEn ? (party.nameEn ?? party.name) : party.name;
    const relation = isEn ? (party.relationEn ?? party.relation) : party.relation;
    const exposure = isEn ? (party.exposureEn ?? party.exposure) : party.exposure;
    return cite(registry, `party-${party.id}`, {
      type: "graph",
      title: partyName,
      snippet: `${relation} · ${L(lang, "敞口", "exposure")} ${exposure}`,
      source: L(lang, "关联方与担保台账", "Related-party & guarantee ledger"),
      metric: exposure,
      confidence: 84,
      capturedAt: company.updatedAt,
      refPath: `/graph?company=${company.id}`,
      refLabel: L(lang, "查看关联方", "View related party"),
    });
  });

  const timelineTitle = latestNegative
    ? isEn
      ? (latestNegative.titleEn ?? latestNegative.title)
      : latestNegative.title
    : "";
  const timelineDesc = latestNegative
    ? isEn
      ? (latestNegative.descEn ?? latestNegative.desc)
      : latestNegative.desc
    : "";
  const timelineNo = latestNegative
    ? cite(registry, `timeline-${latestNegative.id}`, {
        type: "timeline",
        title: timelineTitle,
        snippet: `${latestNegative.date} · ${timelineDesc}`,
        source: L(lang, "变更轨迹 / 公告", "Change trail / announcements"),
        metric: latestNegative.date,
        confidence: 90,
        capturedAt: latestNegative.date,
        refPath: `/company/${company.id}`,
        refLabel: L(lang, "查看变更时间线", "View change timeline"),
      })
    : undefined;

  // --- sections -------------------------------------------------------------
  const section1: ReportSection = {
    id: "overview",
    index: 1,
    title: L(lang, "主体概况与授信结论", "Entity overview & credit conclusion"),
    icon: "ri-file-user-line",
    paragraphs: [
      para("section1-p1", [
        sentence(
          "section1-p1-s1",
          L(
            lang,
            `${name}（${company.nameEn}）是一家注册于${country}的${industry}企业，工商登记编号 ${company.regNo}。`,
            `${company.nameEn} is a ${industry} company registered in ${country}, registration no. ${company.regNo}.`,
          ),
          [regNo],
        ),
        sentence(
          "section1-p1-s2",
          L(
            lang,
            `企业成立于 ${facts.established}，注册资本 ${fRegisteredCapital}，实缴资本 ${fPaidInCapital}，现有员工 ${fEmployees}，当前状态为${fListed}。`,
            `Founded ${facts.established}, with registered capital ${fRegisteredCapital}, paid-in capital ${fPaidInCapital}, ${fEmployees} staff, current status ${fListed}.`,
          ),
          [capNo, scaleNo],
        ),
        sentence(
          "section1-p1-s3",
          L(
            lang,
            `股权结构方面，实际控制人为 ${fActualController}，穿透后${fControllerStake}，法定代表人为 ${fLegalPerson}。`,
            `On ownership, the actual controller is ${fActualController}, holding ${fControllerStake} after look-through, with ${fLegalPerson} as legal representative.`,
          ),
          [controlNo],
        ),
        sentence(
          "section1-p1-s4",
          L(
            lang,
            `外部信用口径参考，${fRatingAgency}；主要往来银行为 ${fMainBanks}，结算方式以${fSettlement}为主。`,
            `External credit reference: ${fRatingAgency}; main banks ${fMainBanks}, settlement primarily ${fSettlement}.`,
          ),
          [ratingNo, bankNo],
        ),
      ]),
      para("section1-p2", [
        sentence(
          "section1-p2-s1",
          L(
            lang,
            `综合信用评估模型结果，该主体信用得分为 ${company.creditScore} 分，对应 ${detail.grade} 级，${detail.gradeNote}。`,
            `Per the composite credit model, the entity scores ${company.creditScore}, grade ${detail.grade}, ${detail.gradeNote}.`,
          ),
          [scoreNo],
        ),
        sentence(
          "section1-p2-s2",
          L(
            lang,
            `12 个月口径违约概率为 ${company.defaultProb}%，${pdDesc}。`,
            `The 12-month default probability is ${company.defaultProb}%, ${pdDesc}.`,
          ),
          [scoreNo],
        ),
        sentence(
          "section1-p2-s3",
          L(
            lang,
            `据此给出参考授信额度 ${company.creditLimit}，风险等级判定为${riskText}。`,
            `Accordingly, a reference credit limit of ${company.creditLimit} is suggested, with risk level ${riskText}.`,
          ),
          [limitNo],
        ),
        sentence("section1-p2-s4", conclusionByRisk[company.riskLevel], [
          benchAllNo,
        ]),
      ]),
    ],
  };

  const flagSentences = flags.slice(0, 4).map((flag) => {
    const ft = flagText(flag);
    return sentence(
      `section2-flag-${flag.id}`,
      L(
        lang,
        `「${ft.label}」（${LEVEL_LABEL[flag.level]} · ${ft.category}）：${ft.desc}`,
        `“${ft.label}” (${LEVEL_LABEL[flag.level]} · ${ft.category}): ${ft.desc}`,
      ),
      [flagNoById.get(flag.id) ?? flagSummaryNo],
    );
  });

  const section2: ReportSection = {
    id: "risk",
    index: 2,
    title: L(lang, "信用与风险表现", "Credit & risk performance"),
    icon: "ri-shield-cross-line",
    paragraphs: [
      para("section2-p1", [
        sentence(
          "section2-p1-s1",
          L(
            lang,
            `本次评估共命中 ${flags.length} 项风险信号，其中高风险 ${highCount} 项、中风险 ${midCount} 项、低风险 ${lowCount} 项，信号分布与主体评分结论相互印证。`,
            `This assessment hit ${flags.length} risk signals — ${highCount} high, ${midCount} medium, ${lowCount} low — corroborating the score conclusion.`,
          ),
          [flagSummaryNo],
        ),
        ...flagSentences,
      ]),
      para("section2-p2", [
        sentence(
          "section2-p2-s1",
          L(
            lang,
            `5C 维度评估中，${weakDim.label}（${weakDim.en}）得分 ${weakDim.score}/100，权重 ${weakDim.weight}%，为相对短板；${strongDim.label}（${strongDim.en}）得分 ${strongDim.score}/100，表现最佳。`,
            `In the 5C assessment, ${weakDim.en} scores ${weakDim.score}/100, weight ${weakDim.weight}%, the relative weak spot; ${strongDim.en} scores ${strongDim.score}/100, the strongest performer.`,
          ),
          [weakDimNo, strongDimNo],
        ),
        sentence(
          "section2-p2-s2",
          complianceFlag
            ? L(
                lang,
                `合规与法务方面，${flagText(complianceFlag).desc}数据来源为${complianceFlag.source}。`,
                `On compliance and legal matters, ${flagText(complianceFlag).desc} Source: ${complianceFlag.source}.`,
              )
            : L(
                lang,
                "合规与法务方面，近三年未命中被执行、重大诉讼与合规处罚记录，合规维度表现稳定。",
                "On compliance and legal matters, no enforcement, major litigation or compliance penalties in the past three years; compliance performance is stable.",
              ),
          [flagSummaryNo],
        ),
      ]),
    ],
  };

  const attributionSentences: ReportSentence[] = [
    sentence(
      "section3-p1-s1",
      L(
        lang,
        `本报告采用 SHAP 加性归因方法，模型基准值为 ${detail.baseValue} 分，最终评分 ${detail.finalScore} 分，共 ${detail.features.length} 项特征参与拆解，其中提分因子 ${detail.positiveCount} 项、扣分因子 ${detail.negativeCount} 项。`,
        `This report uses SHAP additive attribution: model base ${detail.baseValue}, final score ${detail.finalScore}, ${detail.features.length} features in total, with ${detail.positiveCount} positive and ${detail.negativeCount} negative drivers.`,
      ),
      [modelNo],
    ),
  ];
  if (topPos && posFeatureNo) {
    attributionSentences.push(
      sentence(
        "section3-p1-s2",
        L(
          lang,
          `正向贡献最大的因子为「${topPos.label}」，贡献 ${formatContribution(topPos.contribution)}，特征取值为 ${topPos.value}，${topPos.desc}`,
          `The largest positive driver is “${topPos.label}”, contributing ${formatContribution(topPos.contribution)}, feature value ${topPos.value}. ${topPos.desc}`,
        ),
        [posFeatureNo],
      ),
    );
  }
  if (topNeg && negFeatureNo) {
    attributionSentences.push(
      sentence(
        "section3-p1-s3",
        L(
          lang,
          `负向拖累最大的因子为「${topNeg.label}」，贡献 ${formatContribution(topNeg.contribution)}，${topNeg.desc}`,
          `The largest negative dragger is “${topNeg.label}”, contributing ${formatContribution(topNeg.contribution)}. ${topNeg.desc}`,
        ),
        [negFeatureNo],
      ),
    );
  }
  if (secondNeg && neg2FeatureNo) {
    attributionSentences.push(
      sentence(
        "section3-p1-s4",
        L(
          lang,
          `此外，「${secondNeg.label}」贡献 ${formatContribution(secondNeg.contribution)}，同样对最终评分形成压制，需纳入持续观察。`,
          `In addition, “${secondNeg.label}” contributes ${formatContribution(secondNeg.contribution)}, also pressuring the final score and worth ongoing monitoring.`,
        ),
        [neg2FeatureNo],
      ),
    );
  }

  const compareCites = [benchSectorNo, benchSizeNo, benchAllNo].filter(
    (n): n is number => typeof n === "number",
  );
  attributionSentences.push(
    sentence(
      "section3-p1-s5",
      L(
        lang,
        `与社区基准对比，${
          benchSector
            ? `同行业（${benchSector.tag}，样本 ${benchSector.sampleSize} 家，均值 ${benchSector.avgScore} 分）本主体${
                benchSector.diff >= 0 ? "高出" : "低于"
              } ${Math.abs(benchSector.diff)} 分`
            : "同行业基准"
        }；${benchSize ? `${benchSize.tag}组内位于 P${benchSize.percentile}` : ""}，全库基准位于 P${benchAll.percentile}。`,
        `Compared with the community benchmark, this entity is ${
          benchSector
            ? `${
                benchSector.diff >= 0 ? "above" : "below"
              } the sector benchmark (${benchSector.tag}, ${benchSector.sampleSize} firms, avg ${benchSector.avgScore}) by ${Math.abs(benchSector.diff)} pts`
            : "at the sector benchmark"
        }; ${benchSize ? `at P${benchSize.percentile} within the ${benchSize.tag} group` : ""}, and at P${benchAll.percentile} in the library.`,
      ),
      compareCites,
    ),
  );

  const section3: ReportSection = {
    id: "attribution",
    index: 3,
    title: L(lang, "评分归因分析", "Score attribution analysis"),
    icon: "ri-bar-chart-box-line",
    paragraphs: [para("section3-p1", attributionSentences)],
  };

  const penetrationSentences: ReportSentence[] = [
    sentence(
      "section4-p1-s1",
      L(
        lang,
        `经股权、担保与交易关系穿透，以评估主体为中心共识别 ${relatedCount} 个关联主体、${graph.edges.length} 条关系边，覆盖控股股东、子公司、供应商、被担保方与金融机构等类型。`,
        `Through equity, guarantee and trade look-through, ${relatedCount} related entities and ${graph.edges.length} relation edges were identified around the assessed entity, covering controllers, subsidiaries, suppliers, guaranteed parties and financial institutions.`,
      ),
      [graphOverviewNo],
    ),
  ];
  if (topPath && highPaths.length) {
    penetrationSentences.push(
      sentence(
        "section4-p1-s2",
        L(
          lang,
          `模型识别到 ${highPaths.length} 条风险传导链路，其中链路「${topPath.label}」经 ${topPath.hops} 跳传导至评估主体，路径为：${topPath.chain.join(" → ")}。`,
          `The model identified ${highPaths.length} risk transmission chains; chain “${topPath.label}” transmits to the assessed entity in ${topPath.hops} hops, path: ${topPath.chain.join(" → ")}.`,
        ),
        [pathNoById.get(topPath.nodeId) ?? graphOverviewNo],
      ),
    );
  } else {
    penetrationSentences.push(
      sentence(
        "section4-p1-s2",
        L(
          lang,
          "本次穿透未识别到显著的风险传导链路，关联网络整体风险可控。",
          "No significant risk transmission chain was identified; overall related-network risk is manageable.",
        ),
        [graphOverviewNo],
      ),
    );
  }
  penetrationSentences.push(
    guarantors.length
      ? sentence(
          "section4-p1-s3",
          L(
            lang,
            `对外担保方面，${guarantors
              .slice(0, 3)
              .map((g) => `「${isEn ? (g.nameEn ?? g.name) : g.name}」（${isEn ? (g.exposureEn ?? g.exposure) : g.exposure}）`)
              .join("、")}构成担保 / 被担保关系，需重点评估其偿付能力与担保代偿风险。`,
            `On external guarantees, ${guarantors
              .slice(0, 3)
              .map((g) => `“${isEn ? (g.nameEn ?? g.name) : g.name}” (${isEn ? (g.exposureEn ?? g.exposure) : g.exposure})`)
              .join(", ")} form guarantee / guaranteed relationships; their solvency and guarantee compensation risk need priority review.`,
          ),
          guarantorNos,
        )
      : sentence(
          "section4-p1-s3",
          L(
            lang,
            "对外担保方面，未识别到重大对外担保事项，担保维度风险敞口有限。",
            "On external guarantees, no major items were identified; guarantee-dimension exposure is limited.",
          ),
          [graphOverviewNo],
        ),
  );
  if (latestNegative && timelineNo) {
    penetrationSentences.push(
      sentence(
        "section4-p1-s4",
        L(
          lang,
          `值得关注的是，${latestNegative.date} 发生「${timelineTitle}」：${timelineDesc}`,
          `Of note, on ${latestNegative.date} “${timelineTitle}” occurred: ${timelineDesc}`,
        ),
        [timelineNo],
      ),
    );
  }

  const section4: ReportSection = {
    id: "penetration",
    index: 4,
    title: L(lang, "关联方与担保穿透", "Related parties & guarantee look-through"),
    icon: "ri-node-tree",
    paragraphs: [para("section4-p1", penetrationSentences)],
  };

  const section5: ReportSection = {
    id: "recommendation",
    index: 5,
    title: L(lang, "授信建议与风险缓释", "Credit recommendation & mitigation"),
    icon: "ri-shield-check-line",
    paragraphs: [
      para("section5-p1", [
        sentence(
          "section5-p1-s1",
          L(
            lang,
            `综合信用评分、风险信号与关联方穿透结果，对${name}给出参考授信额度 ${company.creditLimit}，风险等级为${riskText}。`,
            `Combining the credit score, risk signals and related-party look-through, a reference credit limit of ${company.creditLimit} is suggested for ${name}, risk level ${riskText}.`,
          ),
          [limitNo],
        ),
        sentence("section5-p1-s2", mitigationByRisk[company.riskLevel], [limitNo]),
        sentence(
          "section5-p1-s3",
          L(
            lang,
            `本报告结论基于 ${detail.evaluatedAt} 的数据快照与模型 ${detail.modelVersion} 生成，若主体经营、股权或对外担保发生重大变化，应重新触发评估。`,
            `This conclusion is based on the ${detail.evaluatedAt} data snapshot and model ${detail.modelVersion}; if operations, ownership or external guarantees change materially, the assessment should be re-triggered.`,
          ),
          [scoreNo],
        ),
      ]),
    ],
  };

  const sections = [section1, section2, section3, section4, section5];

  return {
    id: `RPT-${company.id}`,
    title: L(
      lang,
      `${company.nameCn} · 授信评估报告`,
      `${company.nameEn} · Credit Assessment Report`,
    ),
    subtitle: L(
      lang,
      "基于企业画像、图谱关系与评分归因自动生成",
      "Auto-generated from the company profile, graph relations and score attribution",
    ),
    generatedAt: detail.evaluatedAt,
    modelVersion: detail.modelVersion,
    wordCount: countWords(sections),
    sentenceCount: countSentences(sections),
    sections,
    evidence: registry.evidence,
  };
}

export const evidenceTypeMeta: Record<
  EvidenceType,
  { label: string; labelEn: string; icon: string; tone: string }
> = {
  graph: {
    label: "图谱关系",
    labelEn: "Graph relations",
    icon: "ri-node-tree",
    tone: "text-primary-400 bg-primary-500/12",
  },
  feature: {
    label: "特征值",
    labelEn: "Feature value",
    icon: "ri-bar-chart-box-line",
    tone: "text-accent-400 bg-accent-500/12",
  },
  snapshot: {
    label: "数据快照",
    labelEn: "Data snapshot",
    icon: "ri-database-2-line",
    tone: "text-secondary-300 bg-secondary-500/14",
  },
  fact: {
    label: "工商信息",
    labelEn: "Registration",
    icon: "ri-file-list-3-line",
    tone: "text-secondary-300 bg-secondary-500/14",
  },
  benchmark: {
    label: "社区基准",
    labelEn: "Benchmark",
    icon: "ri-group-2-line",
    tone: "text-accent-400 bg-accent-500/12",
  },
  timeline: {
    label: "变更记录",
    labelEn: "Change record",
    icon: "ri-history-line",
    tone: "text-secondary-300 bg-secondary-500/14",
  },
  flag: {
    label: "风险信号",
    labelEn: "Risk signal",
    icon: "ri-flag-2-line",
    tone: "text-accent-400 bg-accent-500/12",
  },
};

export interface FlatSentence {
  sectionId: string;
  sectionTitle: string;
  sentenceId: string;
}

/** Flattens every sentence in reading order for streaming reveal + progress. */
export function flattenSentences(doc: ReportDoc): FlatSentence[] {
  const list: FlatSentence[] = [];
  doc.sections.forEach((section) => {
    section.paragraphs.forEach((paragraph) => {
      paragraph.sentences.forEach((item) => {
        list.push({
          sectionId: section.id,
          sectionTitle: section.title,
          sentenceId: item.id,
        });
      });
    });
  });
  return list;
}