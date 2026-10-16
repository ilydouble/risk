import { displayEnterpriseProperty } from "@/entities/modeling/lib/enterpriseDisplay";
import Card from "@/shared/ui/Card";

function entries(value: unknown): [string, unknown][] {
  if (Array.isArray(value)) return value.map((item, index) => [`[${index}]`, item]);
  if (value && typeof value === "object") return Object.entries(value);
  return value === undefined ? [] : [["值", value]];
}

export function EnterpriseProperties({ data }: { data: Record<string, unknown> }) {
  const groups = [
    { title: "企业基本字段", subtitle: "已导入的名称、分类和已有标签等字段；标签不等于模型预测。", values: Object.entries(data).filter(([key]) => key !== "attributes" && key !== "features") },
    { title: "企业属性", subtitle: "导入后保存的 attributes，字段含义与单位以来源定义为准。", values: entries(data.attributes) },
    { title: "企业特征", subtitle: "导入后保存的 features；原始值及转换方式可在来源追溯中对照。", values: entries(data.features) },
  ];
  return <>{groups.map(group => <Card key={group.title} title={`${group.title} · ${group.values.length} 项`} subtitle={group.subtitle} icon="ri-file-list-line" bodyClassName="p-5">
    {group.values.length ? <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{group.values.map(([key, value]) => <div key={key} className="min-w-0 rounded-md bg-background-50 p-3"><dt className="break-all text-xs text-foreground-500">{key}</dt><dd className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words text-sm">{displayEnterpriseProperty(value)}</dd></div>)}</dl> : <p className="text-sm text-foreground-500">此记录没有该组字段；其他字段请查看相邻区域。</p>}
  </Card>)}</>;
}
