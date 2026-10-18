import { ChevronDown, CircleCheck, FileChartColumn, Info } from "lucide-react";
import type { Item } from "@/entities/assistant/model/types";
import { useLang } from "@/shared/lib/useLang";

type FinancialReference = NonNullable<Extract<Item, { kind: "tool_call" }>["financialPrediction"]>;

const warningsZh: Record<string, string> = {
  "Matched research-cohort scores are not population default probabilities.": "分数适用于匹配研究队列，不代表企业总体违约概率。",
  "CPU/dtype/batch changes require separate numerical validation.": "更换设备、精度或批次后需要单独进行数值验证。",
  "Calibration is unavailable.": "当前未提供正式校准参数，展示原始候选分数。",
  "Calibration applies to the matched research cohort only.": "校准结果仅适用于匹配研究队列。",
  "No observed financial values; loading probe or missing-data case only.": "当前输入没有已观测财务数值，仅为缺失数据情形。",
};

export function FinancialRiskResultCard({ reference }: { reference: FinancialReference }) {
  const { pick } = useLang();
  const percent = (value: number) => `${(value * 100).toFixed(2)}%`;
  // This is a display conversion of the raw event score, without a new risk threshold.
  const riskScore = (reference.eventScore * 100).toFixed(2);
  const hasCalibration = reference.calibratedEventScore != null;
  const scores = [
    { label: pick("无破产事件候选", "No-insolvency candidate"), value: reference.noEventScore, color: "bg-primary-500" },
    { label: pick("破产事件候选", "Insolvency candidate"), value: reference.eventScore, color: "bg-amber-500" },
  ];
  return <section aria-label={pick("企业财务风险评估", "Company financial risk assessment")}
    className="space-y-4 rounded-xl bg-background-50 p-1 text-sm">
    <header className="flex items-start gap-3">
      <div className="rounded-lg bg-primary-500/10 p-2 text-primary-500"><FileChartColumn size={20} aria-hidden="true" /></div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-foreground-500">{pick("企业财务风险评估", "Company financial risk assessment")}</p>
        <h3 className="mt-1 break-words font-medium text-foreground-800">{reference.companyName || reference.companyId}</h3>
        {reference.companyName && reference.companyName !== reference.companyId && <p className="mt-1 break-all text-xs text-foreground-400">
          {pick("企业编号", "Company number")}：{reference.companyId}
        </p>}
      </div>
      <span className="flex shrink-0 items-center gap-1 rounded-full bg-primary-500/10 px-2 py-1 text-xs text-primary-600">
        <CircleCheck size={12} aria-hidden="true" />{pick("已保存", "Saved")}
      </span>
    </header>
    <div className="space-y-4 rounded-lg border border-primary-500/15 bg-primary-500/5 p-4 sm:p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="font-medium text-foreground-700">{pick("破产风险参考分", "Insolvency risk reference score")}</p>
        <p className="flex items-baseline gap-2 font-mono tabular-nums">
          <strong className="text-4xl font-semibold tracking-tight text-foreground-800">{riskScore}</strong>
          <span className="text-sm text-foreground-400">/ 100</span>
        </p>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-background-200" aria-hidden="true">
        <div className="h-full rounded-full bg-primary-500" style={{ width: `${reference.eventScore * 100}%` }} />
      </div>
      <p className="text-xs leading-5 text-foreground-500">{pick(
        "分值越高，模型越倾向于发生正式破产事件。",
        "Higher scores indicate a stronger model preference for a formal insolvency event.",
      )}</p>
    </div>
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs text-foreground-600">
      <div><dt className="text-foreground-400">{pick("财务观测月份", "Financial observation month")}</dt><dd className="mt-1">{reference.observationMonth ?? pick("未提供", "Not provided")}</dd></div>
      <div><dt className="text-foreground-400">{pick("预测期限", "Prediction horizon")}</dt><dd className="mt-1">{pick("观测期后 12 个月", "12 months after the observation")}</dd></div>
    </dl>
    <p className="text-xs leading-5 text-foreground-500">{hasCalibration
      ? pick("此处展示原始模型参考分，不代表实际破产概率；校准结果见详情。", "This raw model reference score is not an actual insolvency probability; see details for calibration.")
      : pick("当前分数尚未校准为实际破产概率，仅供风险参考。", "This score has not been calibrated to an actual insolvency probability; use it as a risk reference only.")}</p>
    <details className="group border-t border-background-200 pt-3">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-md py-1 text-xs text-foreground-500 transition-colors hover:text-foreground-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 [&::-webkit-details-marker]:hidden">
        {pick("模型与计算详情", "Model and calculation details")}
        <ChevronDown size={15} aria-hidden="true" className="shrink-0 transition-transform group-open:rotate-180 motion-reduce:transition-none" />
      </summary>
      <div className="space-y-4 pt-4">
        <dl className="grid grid-cols-1 gap-x-4 gap-y-3 text-xs text-foreground-500 sm:grid-cols-2">
          <div><dt className="text-foreground-400">{pick("模型版本", "Model version")}</dt><dd className="mt-1 break-all">{reference.modelVersion}</dd></div>
          <div><dt className="text-foreground-400">{pick("已提供特征", "Provided features")}</dt><dd className="mt-1">{reference.featureCount}</dd></div>
          <div><dt className="text-foreground-400">{pick("校准状态", "Calibration status")}</dt><dd className="mt-1">{hasCalibration ? pick("已提供校准参数", "Calibration parameters available") : pick("未提供校准参数", "Calibration parameters unavailable")}</dd></div>
          <div><dt className="text-foreground-400">{pick("保存时间", "Saved at")}</dt><dd className="mt-1">{new Intl.DateTimeFormat(pick("zh-CN", "en-GB"), { dateStyle: "medium", timeStyle: "short" }).format(new Date(reference.createdAt))}</dd></div>
          <div><dt className="text-foreground-400">{pick("预测记录 ID", "Prediction record ID")}</dt><dd className="mt-1 break-all font-mono">{reference.predictionId}</dd></div>
          <div><dt className="text-foreground-400">{pick("输入摘要", "Input digest")}</dt><dd className="mt-1 break-all font-mono">{reference.inputSha256}</dd></div>
        </dl>
        <div className="space-y-3 rounded-lg border border-background-200 p-3">
          <p className="text-xs font-medium text-foreground-500">{pick("原始候选分数", "Raw candidate scores")}</p>
          {scores.map(score => <div key={score.label}>
            <div className="mb-1.5 flex items-center justify-between gap-3 text-xs">
              <span className="text-foreground-500">{score.label}</span>
              <span className="font-mono font-medium tabular-nums">{percent(score.value)}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-background-200" aria-hidden="true">
              <div className={`h-full rounded-full ${score.color}`} style={{ width: `${score.value * 100}%` }} />
            </div>
          </div>)}
          <p className="text-xs leading-5 text-foreground-400">{pick("参考分 = 原始破产事件候选分数 × 100，不另设风险分级阈值。", "Reference score = raw insolvency candidate score × 100; no risk-grade thresholds are applied.")}</p>
          {reference.calibratedEventScore != null && <p className="text-xs text-foreground-500">
            {pick("校准后的破产事件分数", "Calibrated insolvency event score")}：{percent(reference.calibratedEventScore)}
          </p>}
        </div>
        <div className="flex gap-2 rounded-lg bg-background-100 p-3 text-xs leading-5 text-foreground-500">
          <Info size={15} aria-hidden="true" className="mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p>{pick("目标：观测期后 12 个月首次观察到主要正式破产程序。", "Target: first observed primary formal insolvency within 12 months after the observation.")}</p>
            {reference.limitations.map(message => <p key={message}>{pick(warningsZh[message] ?? message, message)}</p>)}
          </div>
        </div>
      </div>
    </details>
  </section>;
}
