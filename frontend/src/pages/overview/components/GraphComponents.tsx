import { useTranslation } from "react-i18next";
import type { components } from "@/shared/api/generated/schema";

type GraphComponentDTO = components["schemas"]["GraphComponentDTO"];
type EdgeTypeItemDTO = components["schemas"]["EdgeTypeItemDTO"];

export default function GraphComponents({ components: items, edgeTypes }: { components: GraphComponentDTO[]; edgeTypes: EdgeTypeItemDTO[] }) {
  const { t } = useTranslation();
  return <div className="space-y-4 p-4">
    <div className="grid grid-cols-2 gap-3">{items.map((item) => <div key={item.key} className="rounded-md border border-background-200 bg-background-50 p-3">
      <p className="text-[11px] text-foreground-500">{t(`overview.graph.${item.key}`)}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-foreground-950">{item.rowCount.toLocaleString()}</p>
      <p className="mt-1 text-[11px] text-foreground-500">{t("overview.graph.groups", { count: item.groupCount.toLocaleString() })}</p>
    </div>)}</div>
    <div><p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-foreground-500">{t("overview.graph.edgeTypes")}</p>
      <div className="space-y-1.5">{edgeTypes.map((item) => <div key={item.type} className="flex items-center justify-between gap-3 text-xs"><span className="truncate font-mono text-foreground-700">{item.type}</span><span className="font-mono text-foreground-900">{item.count.toLocaleString()}</span></div>)}</div>
    </div>
  </div>;
}
