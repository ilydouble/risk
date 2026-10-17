import { Link, useSearchParams } from "react-router-dom";
import type { Item } from "@/entities/assistant/model/types";

function CaseLink({ preparationId }: { preparationId: string }) {
  const [params] = useSearchParams();
  const target = new URLSearchParams({ preparation: preparationId });
  const conversation = params.get("conversation");
  if (conversation) target.set("conversation", conversation);
  return <Link className="inline-block text-xs text-primary-500 underline" to={`/chat?${target}`}>查看方案、核验结果与导入入口 →</Link>;
}

export function PreparationResultLink({ item }: { item: Extract<Item, { kind: "tool_call" }> }) {
  const result = Array.isArray(item.result) ? item.result.find(block => block && typeof block === "object" && "json" in block)?.json : undefined;
  const caseId = item.name.startsWith("preparation_") && result && typeof result === "object" && "preparationId" in result && typeof result.preparationId === "string" ? result.preparationId : undefined;
  return caseId ? <CaseLink preparationId={caseId} /> : null;
}
