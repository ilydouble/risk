import { displayEnterpriseProperty } from "@/entities/modeling/lib/enterpriseDisplay";
import type { ResponseEnterpriseProvenance } from "@/shared/api/generated/schema";
import Card from "@/shared/ui/Card";

const types = { text: "文本", number: "数值", integer: "整数", label: "标签值映射", ignore: "忽略" };
const missing = { reject: "拒绝记录", null: "保留为 null", fill: "填充" };

export function EnterpriseSourceTrace({ provenance }: { provenance?: ResponseEnterpriseProvenance | null }) {
  const available = provenance?.status === "available";
  return <Card title="原始记录与来源追溯" subtitle="对照导入时的原始值和冻结规则；后续编辑源案例不会改变本次导入的解释。" icon="ri-history-line" bodyClassName="space-y-4 p-5">
    <p className="text-sm text-foreground-500">{provenance?.message || "此数据集尚未提供原始记录追溯信息。"}</p>
    {available && <>
      <div className="flex flex-wrap items-start justify-between gap-3 text-sm">
        <div><p className="break-all font-medium">原文件：{provenance.filename}</p><p className="mt-2 text-foreground-500">第 {provenance.sourceRow} 条数据记录 · CSV 第 {provenance.sourceLine}{provenance.sourceEndLine !== provenance.sourceLine ? `–${provenance.sourceEndLine}` : ""} 行 · 表头不计入数据记录数</p></div>
      </div>
      {Boolean(provenance.duplicateCount) && <p className="rounded-lg bg-background-50 p-3 text-xs leading-6">本企业另有 {provenance.duplicateCount} 条内容完全相同的原始记录已去重，未生成额外企业。重复行起始位置：{provenance.duplicateLines?.join("、")}{provenance.duplicatesTruncated ? "（仅展示前100条）" : ""}。</p>}
      {provenance.labelMeaning && <p className="text-sm leading-6">导入时标签定义：{provenance.labelMeaning}</p>}
      <p className="text-xs text-foreground-500">导入时去重规则：{provenance.deduplicate === "exact" ? "原始内容完全相同的行保留一条" : "不自动去重，重复企业标识会阻止导入"}。</p>
      <div className="overflow-x-auto"><table className="min-w-full text-left text-xs"><thead><tr>{["原始字段", "原始值", "导入字段", "导入后值", "导入时处理规则"].map(name => <th key={name} className="whitespace-nowrap border-b border-background-200 p-3">{name}</th>)}</tr></thead><tbody>{provenance.fields?.map(field => <tr key={field.rule.field} className="border-b border-background-200 align-top">
        <td className="min-w-36 break-all p-3 font-medium">{field.rule.field}</td>
        <td className="min-w-40 max-w-80 p-3"><div className="max-h-40 overflow-auto whitespace-pre-wrap break-words">{displayEnterpriseProperty(field.originalValue)}</div>{field.originalTruncated && <p className="mt-1 text-amber-600">原值超过4096字符，展示已截断；完整值保留在原文件中。</p>}</td>
        <td className="min-w-40 break-all p-3">{field.ignored ? "未导入" : field.rule.target}</td>
        <td className="min-w-40 max-w-80 p-3"><div className="max-h-40 overflow-auto whitespace-pre-wrap break-words">{field.ignored ? "未导入（按规则忽略）" : displayEnterpriseProperty(field.convertedValue)}</div>{field.convertedTruncated && <p className="mt-1 text-amber-600">导入值展示已截断。</p>}</td>
        <td className="min-w-60 max-w-96 space-y-1 break-words p-3 text-foreground-500"><p>{types[field.rule.type]}</p>{!field.ignored && <><p>缺失：{missing[field.rule.missing ?? "reject"]}{field.rule.missing === "fill" ? ` → ${displayEnterpriseProperty(field.rule.fill)}` : ""}</p><p>识别为缺失：{JSON.stringify(field.rule.missingValues)}</p>{field.rule.type === "label" && <p>标签映射：{JSON.stringify(field.rule.values)}</p>}</>}</td>
      </tr>)}</tbody></table></div>
      <details className="text-xs"><summary className="cursor-pointer text-foreground-600">查看文件摘要与版本依据</summary><dl className="mt-3 space-y-2 break-all leading-6">{[["源案例", provenance.preparationId], ["转换任务", provenance.taskId], ["执行器", provenance.engineVersion], ["冻结规则版本", provenance.planVersion], [provenance.engineVersion === "enterprise-case-v1" ? "案例文件集合 SHA-256" : "原文件 SHA-256", provenance.sourceSha256], ["转换产物 SHA-256", provenance.outputSha256], ["导入时间", provenance.importedAt ? new Date(provenance.importedAt).toLocaleString() : "—"]].map(([label, value]) => <div key={label}><dt className="text-foreground-500">{label}</dt><dd>{value}</dd></div>)}</dl></details>
    </>}
  </Card>;
}
