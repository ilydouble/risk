import { demoSeedCompanies } from "@/features/demo-scenarios/model/fixtures/seedCases";
import { resolveProfile } from "@/features/demo-scenarios/lib/profile";
import { buildScoreDetail, MODEL_VERSION } from "@/features/demo-scenarios/lib/score";
import { riskLabel, riskLabelEn } from "@/features/demo-scenarios/lib/graph";
import type {
  BatchRiskCount,
  BatchRow,
  BatchRowStatus,
  BatchRoster,
  BatchRun,
  BatchSummary,
  Company,
  ReproduceStep,
} from "@/entities/demo/model/types";

export type Lang = "zh" | "en";

const L = (lang: Lang, zh: string, en: string): string =>
  lang === "en" ? en : zh;

const isEn = (lang: Lang): boolean => lang === "en";

export function getStatusMeta(
  lang: Lang,
): Record<
  BatchRowStatus,
  { label: string; icon: string; className: string }
> {
  return {
    ok: {
      label: L(lang, "已评分", "Scored"),
      icon: "ri-checkbox-circle-line",
      className: "border-primary-400/40 bg-primary-500/10 text-primary-400",
    },
    review: {
      label: L(lang, "需复核", "Needs review"),
      icon: "ri-error-warning-line",
      className: "border-accent-500/40 bg-accent-500/10 text-accent-400",
    },
    unmatched: {
      label: L(lang, "未匹配", "Unmatched"),
      icon: "ri-question-line",
      className: "border-background-300 bg-background-200/70 text-foreground-500",
    },
  };
}

export function statusLabel(status: BatchRowStatus, lang: Lang): string {
  return getStatusMeta(lang)[status].label;
}

function outcomeFor(level: keyof typeof OUTCOME_MAP, lang: Lang): string {
  const zh = OUTCOME_MAP[level];
  const en = OUTCOME_MAP_EN[level];
  return L(lang, zh, en);
}

const OUTCOME_MAP = {
  low: "建议通过",
  medium: "有条件通过",
  high: "建议不新增授信",
} as const;

const OUTCOME_MAP_EN: Record<keyof typeof OUTCOME_MAP, string> = {
  low: "Recommend approval",
  medium: "Conditional approval",
  high: "Do not add new credit",
};

function hash(input: string): number {
  let value = 0;
  for (let i = 0; i < input.length; i += 1) {
    value = (value * 31 + input.charCodeAt(i)) >>> 0;
  }
  return value;
}

function nowStamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(
    d.getHours(),
  )}:${p(d.getMinutes())}`;
}

function normalize(text: string): string {
  return text.trim().toLowerCase().replace(/\s+/g, "");
}

/* ------------------------------------------------------------------ */
/* Roster parsing                                                      */
/* ------------------------------------------------------------------ */

/** Reads the first cell of a CSV line, honoring a quoted field with commas. */
function firstCell(line: string): string {
  const quoted = line.match(/^\s*"([^"]*)"\s*(?:[,\t;]|$)/);
  if (quoted) return quoted[1].trim();
  return (line.split(/[,\t;]/)[0] ?? "")
    .trim()
    .replace(/^["']|["']$/g, "");
}

export function parseRosterCsv(text: string): string[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const names: string[] = [];
  lines.forEach((line, index) => {
    const first = firstCell(line);
    if (!first) return;
    if (index === 0 && /名称|name/i.test(first)) return; // header row
    names.push(first);
  });
  return names;
}

export function matchCompany(name: string): Company | undefined {
  const key = normalize(name);
  if (!key) return undefined;
  return demoSeedCompanies.find(
    (company) =>
      normalize(company.nameCn) === key ||
      normalize(company.nameEn) === key ||
      normalize(company.regNo) === key,
  );
}

function buildRoster(
  text: string,
  fileName: string,
  source: BatchRoster["source"],
  fileNameEn?: string,
): BatchRoster {
  const rawNames = parseRosterCsv(text);
  const valid = rawNames.filter((name) => matchCompany(name)).length;
  return {
    fileName,
    fileNameEn,
    source,
    importedAt: nowStamp(),
    rawNames,
    valid,
    invalid: rawNames.length - valid,
  };
}

export function makeRosterFromText(
  text: string,
  fileName: string,
): BatchRoster {
  return buildRoster(text, fileName, "file");
}

export function createSampleRoster(csv: string): BatchRoster {
  return buildRoster(
    csv,
    "示例名单-跨境授信批次.csv",
    "sample",
    "sample-roster-cross-border-batch.csv",
  );
}

/* ------------------------------------------------------------------ */
/* Rows                                                                */
/* ------------------------------------------------------------------ */

export function buildBatchRows(names: string[], lang: Lang = "zh"): BatchRow[] {
  const seen = new Map<string, number>();
  const en = isEn(lang);

  const rows: BatchRow[] = names.map((rawName, index) => {
    const rowNo = index + 1;
    const company = matchCompany(rawName);

    if (!company) {
      return {
        id: `B-${rowNo}`,
        rowNo,
        rawName,
        matched: false,
        duplicate: false,
        nameCn: rawName,
        nameEn: "—",
        country: "—",
        countryEn: "—",
        region: "—",
        sector: "—",
        industry: "—",
        industryEn: "—",
        creditScore: 0,
        grade: "—",
        riskLevel: "medium",
        defaultProb: 0,
        creditLimit: "—",
        outcome: L(lang, "待人工建档", "Pending onboarding"),
        status: "unmatched",
        issues: [
          L(
            lang,
            "未在企业授信库中匹配到主体，需补充工商信息后重新评分",
            "No entity matched in the credit library; add business registry info and re-score",
          ),
        ],
        rank: null,
      };
    }

    const profile = resolveProfile(company);
    const detail = buildScoreDetail(company, profile, lang);
    const issues: string[] = [];

    const ratingAgency = en
      ? (profile.factsEn?.ratingAgency ?? profile.facts.ratingAgency)
      : profile.facts.ratingAgency;

    const paidMatch = profile.facts.paidInCapital.match(/(\d+)\s*%/);
    const paidRatio = paidMatch ? Number(paidMatch[1]) : 100;
    if (/暂无|无有效|负面/.test(profile.facts.ratingAgency)) {
      issues.push(
        L(
          lang,
          `外部评级「${ratingAgency}」，需人工复核`,
          `External rating "${ratingAgency}"; manual review required`,
        ),
      );
    }
    if (paidRatio < 50) {
      issues.push(
        L(
          lang,
          `注册资本实缴比例仅 ${paidRatio}%`,
          `Paid-in capital ratio is only ${paidRatio}%`,
        ),
      );
    }
    if (company.riskLevel === "high") {
      issues.push(
        L(
          lang,
          "命中高风险准入拦截规则，建议人工复核",
          "Blocked by a high-risk admission rule; manual review advised",
        ),
      );
    }

    const duplicate = seen.has(company.id);
    if (duplicate) {
      issues.push(
        L(
          lang,
          `与名单第 ${seen.get(company.id)} 行重复，已自动去重`,
          `Duplicate of row ${seen.get(company.id)} in the list; auto de-duplicated`,
        ),
      );
    } else {
      seen.set(company.id, rowNo);
    }

    const status: BatchRowStatus =
      duplicate || issues.length > 0 ? "review" : "ok";

    return {
      id: `B-${rowNo}`,
      rowNo,
      rawName,
      matched: true,
      duplicate,
      companyId: company.id,
      nameCn: company.nameCn,
      nameEn: company.nameEn,
      country: company.country,
      countryEn: company.countryEn,
      region: company.region,
      sector: company.sector,
      industry: company.industry,
      industryEn: company.industryEn,
      creditScore: company.creditScore,
      grade: detail.grade,
      riskLevel: company.riskLevel,
      defaultProb: company.defaultProb,
      creditLimit: company.creditLimit,
      outcome: outcomeFor(company.riskLevel, lang),
      status,
      issues,
      rank: null,
    };
  });

  const ranked = rows
    .filter((row) => row.matched && !row.duplicate)
    .sort(
      (a, b) => b.creditScore - a.creditScore || a.defaultProb - b.defaultProb,
    );
  ranked.forEach((row, index) => {
    row.rank = index + 1;
  });

  return rows;
}

/* ------------------------------------------------------------------ */
/* Summary                                                             */
/* ------------------------------------------------------------------ */

export function buildBatchSummary(
  rows: BatchRow[],
  lang: Lang = "zh",
): BatchSummary {
  const unique = rows.filter((row) => row.matched && !row.duplicate);
  const matched = rows.filter((row) => row.matched).length;
  const scoreSum = unique.reduce((sum, row) => sum + row.creditScore, 0);

  const levels: BatchRiskCount[] = (["low", "medium", "high"] as const).map(
    (level) => ({
      level,
      label: riskLabel[level],
      labelEn: riskLabelEn[level],
      count: unique.filter((row) => row.riskLevel === level).length,
    }),
  );

  return {
    total: rows.length,
    matched,
    unmatched: rows.filter((row) => !row.matched).length,
    duplicate: rows.filter((row) => row.duplicate).length,
    review: rows.filter((row) => row.status === "review").length,
    highRisk: unique.filter((row) => row.riskLevel === "high").length,
    avgScore: unique.length ? Math.round(scoreSum / unique.length) : 0,
    countries: new Set(unique.map((row) => row.countryEn ?? row.country)).size,
    riskDistribution: levels,
  };
}

/* ------------------------------------------------------------------ */
/* Run                                                                 */
/* ------------------------------------------------------------------ */

export function buildBatchRun(
  roster: BatchRoster,
  lang: Lang = "zh",
): BatchRun {
  const count = roster.rawNames.length;
  const steps: ReproduceStep[] = [
    {
      label: L(lang, "解析名单文件", "Parse list file"),
      detail: L(
        lang,
        `读取「${roster.fileName}」并识别 ${count} 条企业记录`,
        `Read "${roster.fileName}" and identify ${count} company records`,
      ),
      durationMs: 420,
    },
    {
      label: L(lang, "字段校验与标准化", "Field validation & normalization"),
      detail: L(
        lang,
        `清洗企业名称、统一社会信用代码与来源字段，标准化 ${count} 条记录`,
        `Clean company names, registration numbers and source fields; normalized ${count} records`,
      ),
      durationMs: 560,
    },
    {
      label: L(lang, "企业库主体匹配", "Entity matching against the library"),
      detail: L(
        lang,
        `与授信库 ${demoSeedCompanies.length} 家主体比对，命中 ${roster.valid} 家`,
        `Compared against ${demoSeedCompanies.length} entities in the credit library, matched ${roster.valid}`,
      ),
      durationMs: 780,
    },
    {
      label: L(lang, "批量评分与风险分级", "Batch scoring & risk grading"),
      detail: L(
        lang,
        `使用样例数据模拟 ${MODEL_VERSION} 信用分、等级与违约概率`,
        `Simulate ${MODEL_VERSION} scores, grades and default probabilities from sample data`,
      ),
      durationMs: 940,
    },
    {
      label: L(lang, "排序与结果汇总", "Ranking & result summary"),
      detail: L(
        lang,
        "按信用分降序排名，标记异常与重复记录并生成结果表",
        "Rank by credit score desc, flag anomalies and duplicates, and build the result table",
      ),
      durationMs: 480,
    },
  ];

  const totalMs = steps.reduce((sum, step) => sum + step.durationMs, 0);
  const seed = hash(`${roster.fileName}:${roster.rawNames.join("|")}`);

  return {
    id: `BATCH-${seed.toString(16).toUpperCase().slice(0, 6)}`,
    modelVersion: MODEL_VERSION,
    startedAt: nowStamp(),
    duration: `${(totalMs / 1000).toFixed(2)} s`,
    scanned: count,
    steps,
  };
}

/* ------------------------------------------------------------------ */
/* CSV export                                                          */
/* ------------------------------------------------------------------ */

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function buildResultCsv(rows: BatchRow[], lang: Lang = "zh"): string {
  const header = [
    L(lang, "排名", "Rank"),
    L(lang, "企业名称", "Company (CN)"),
    L(lang, "英文名称", "Company (EN)"),
    L(lang, "国别/地区", "Country / region"),
    L(lang, "行业", "Industry"),
    L(lang, "信用分", "Credit score"),
    L(lang, "信用等级", "Credit grade"),
    L(lang, "风险等级", "Risk level"),
    L(lang, "违约概率(%)", "Default prob. (%)"),
    L(lang, "参考授信额度", "Ref. credit limit"),
    L(lang, "建议结论", "Recommendation"),
    L(lang, "处理状态", "Status"),
    L(lang, "备注", "Notes"),
  ];

  const body = rows.map((row) => [
    row.rank ? String(row.rank) : "",
    row.nameCn,
    row.nameEn,
    isEn(lang) ? (row.countryEn ?? row.country) : row.country,
    isEn(lang) ? (row.industryEn ?? row.industry) : row.industry,
    row.matched ? String(row.creditScore) : "",
    row.grade,
    row.matched ? L(lang, riskLabel[row.riskLevel], riskLabelEn[row.riskLevel]) : "",
    row.matched ? row.defaultProb.toFixed(1) : "",
    row.creditLimit,
    row.outcome,
    statusLabel(row.status, lang),
    row.issues.join("；"),
  ]);

  return [header, ...body]
    .map((cells) => cells.map((cell) => csvCell(cell)).join(","))
    .join("\n");
}
