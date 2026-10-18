import { CircleCheck, FileChartColumn, ShieldCheck } from "lucide-react";
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
  const scores = [
    { label: pick("无事件候选", "No-event candidate"), value: reference.noEventScore, color: "bg-primary-500" },
    { label: pick("事件候选", "Event candidate"), value: reference.eventScore, color: "bg-amber-500" },
  ];
  return <section aria-label={pick("财务模型预测结果", "Financial model prediction")}
    className="space-y-4 rounded-xl bg-background-50 p-1 text-sm">
    <header className="flex items-start gap-3">
      <div className="rounded-lg bg-primary-500/10 p-2 text-primary-500"><FileChartColumn size={20} /></div>
      <div className="min-w-0 flex-1">
        <p className="break-words font-medium text-foreground-800">{reference.companyName}</p>
        <p className="mt-1 break-all text-xs text-foreground-400">{reference.companyId} · {reference.modelVersion}</p>
      </div>
      <span className="flex shrink-0 items-center gap-1 rounded-full bg-primary-500/10 px-2 py-1 text-xs text-primary-600">
        <CircleCheck size={12} />{pick("已保存", "Saved")}
      </span>
    </header>
    <div className="rounded-lg border border-background-200 p-3 sm:p-4">
      <p className="mb-3 text-xs font-medium text-foreground-500">{pick("原始候选分数", "Raw candidate scores")}</p>
      <div className="space-y-3">
        {scores.map(score => <div key={score.label}>
          <div className="mb-1.5 flex items-center justify-between gap-3 text-xs">
            <span className="text-foreground-500">{score.label}</span>
            <span className="font-mono font-medium tabular-nums">{percent(score.value)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-background-200" aria-hidden="true">
            <div className={`h-full rounded-full ${score.color}`} style={{ width: `${score.value * 100}%` }} />
          </div>
        </div>)}
      </div>
      {reference.calibratedEventScore != null && <p className="mt-3 text-xs text-foreground-500">
        {pick("校准后的事件分数", "Calibrated event score")}：{percent(reference.calibratedEventScore)}
      </p>}
    </div>
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs text-foreground-500 sm:grid-cols-3">
      <div><dt className="text-foreground-400">{pick("观测期", "Observation")}</dt><dd className="mt-1">{reference.observationMonth ?? pick("未提供", "Not provided")}</dd></div>
      <div><dt className="text-foreground-400">{pick("已提供特征", "Provided features")}</dt><dd className="mt-1">{reference.featureCount}</dd></div>
      <div><dt className="text-foreground-400">{pick("预测记录", "Prediction record")}</dt><dd title={reference.predictionId} className="mt-1 font-mono">{reference.predictionId.slice(0, 8)}</dd></div>
    </dl>
    <div className="flex gap-2 rounded-lg bg-amber-500/5 p-3 text-xs leading-5 text-foreground-500">
      <ShieldCheck size={15} className="mt-0.5 shrink-0 text-amber-600" />
      <div className="space-y-1">
        <p>{pick("目标：未来 12 个月首次观察到主要正式破产程序。", "Target: first observed primary formal insolvency within 12 months.")}</p>
        {reference.limitations.map(message => <p key={message}>{pick(warningsZh[message] ?? message, message)}</p>)}
      </div>
    </div>
    <p className="text-xs text-foreground-400" title={reference.inputSha256}>
      {new Intl.DateTimeFormat(pick("zh-CN", "en-GB"), { dateStyle: "medium", timeStyle: "short" }).format(new Date(reference.createdAt))}
      {" · "}{pick("输入摘要", "Input digest")} {reference.inputSha256.slice(0, 10)}
    </p>
  </section>;
}
