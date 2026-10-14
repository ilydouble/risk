import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  requestImportEnterprises,
  requestListEnterpriseRecords,
  requestPredictModel,
} from "@/entities/modeling/api/modelingApi";
import type {
  RequestListEnterpriseRecords,
  ResponseListEnterpriseRecords,
} from "@/shared/api/generated/schema";
import type { useModelingWorkbench } from "@/features/modeling/model/useModelingWorkbench";
import { handleApiError } from "@/shared/api/http";
import { button, input } from "./presentation";

type Workbench = ReturnType<typeof useModelingWorkbench>;
type Kind = NonNullable<RequestListEnterpriseRecords["kind"]>;

function display(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function EnterpriseDataPanel({ work }: { work: Workbench }) {
  const { t } = useTranslation();
  const [result, setResult] = useState<ResponseListEnterpriseRecords>();
  const [kind, setKind] = useState<Kind>("company");
  const [keyword, setKeyword] = useState("");
  const [node, setNode] = useState<{ id: string; snapshot: string }>();
  const [page, setPage] = useState(1);
  const [modelId, setModelId] = useState("");
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const models = work.models.filter((model) =>
    work.runs.some((run) => run.id === model.runId && run.datasetId === work.datasetId),
  );
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const timer = setTimeout(() => {
      void requestListEnterpriseRecords({
        datasetId: work.datasetId,
        kind,
        keyword,
        nodeId: node?.id,
        snapshot: node?.snapshot,
        modelId: modelId || undefined,
        pagination: { page, pageSize: 20 },
      }).then((data) => {
        if (active) setResult(data);
      }).catch((reason: unknown) => {
        if (active) setError(handleApiError(reason));
      }).finally(() => {
        if (active) setLoading(false);
      });
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [work.datasetId, kind, keyword, node, modelId, page, revision]);

  const act = async (operation: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await operation();
      setRevision((value) => value + 1);
    } catch (reason) {
      setError(handleApiError(reason, {
        MODELING_ENTERPRISE_UNAVAILABLE: t("modeling.enterprise.reupload"),
        MODELING_ENTERPRISE_INVALID: t("modeling.enterprise.invalid"),
        RISKGNN_COMPANY_NOT_FOUND: t("modeling.enterprise.outsideGraph"),
      }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-3 border-t border-background-200 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold">{t("modeling.enterprise.title")}</h3>
        <div className="flex gap-3 text-xs text-primary-400">
          <Link to={`/?source=uploaded&dataset=${encodeURIComponent(work.datasetId)}`}>查看总览</Link>
          <Link to={`/search?source=uploaded&dataset=${encodeURIComponent(work.datasetId)}`}>进入企业检索</Link>
        </div>
      </div>
      <p className="text-xs text-foreground-500">校验完成后会自动导入，并接入总览与主导航企业检索；也可手动导入或重试。</p>
      <p className="text-xs text-foreground-500">{t("modeling.enterprise.note")}</p>
      {error && <p role="alert" className="text-sm text-danger-500">{error}</p>}
      {loading && <p role="status" className="text-sm">{t("modeling.enterprise.loading")}</p>}
      {!loading && !result && (
        <button className={button} onClick={() => setRevision((value) => value + 1)}>
          {t("modeling.enterprise.retry")}
        </button>
      )}
      {result && !result.imported && (
        <button className={button} disabled={busy || loading} onClick={() => void act(() =>
          requestImportEnterprises({ datasetId: work.datasetId }),
        )}>
          {t(busy ? "modeling.enterprise.importing" : "modeling.enterprise.import")}
        </button>
      )}
      {result?.imported && (
        <>
          <p className="text-xs text-foreground-500">
            {Object.entries(result.counts).map(([key, count]) =>
              `${t(`modeling.enterprise.kinds.${key}`)}: ${count.toLocaleString()}`,
            ).join(" · ")}
          </p>
          <div className="flex flex-wrap gap-2">
            <select disabled={busy} className={input} aria-label={t("modeling.enterprise.kind")}
              value={kind} onChange={(event) => {
                setKind(event.target.value as Kind); setPage(1); setKeyword("");
              }}>
              {(["company", "person", "edge", "hyperedge", "event"] as const).map((key) => (
                <option key={key} value={key}>{t(`modeling.enterprise.kinds.${key}`)}</option>
              ))}
            </select>
            {(kind === "company" || kind === "person") && (
              <input disabled={busy} className={input} aria-label={t("modeling.enterprise.search")}
                placeholder={t("modeling.enterprise.search")} value={keyword}
                onChange={(event) => { setKeyword(event.target.value); setPage(1); }} />
            )}
            <select disabled={busy} className={input} aria-label={t("modeling.enterprise.model")}
              value={modelId} onChange={(event) => { setModelId(event.target.value); setPage(1); }}>
              <option value="">{t("modeling.enterprise.noModel")}</option>
              {models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
            </select>
          </div>
          {modelId && <p className="text-xs text-foreground-500">{t("modeling.enterprise.graphNote")}</p>}
          {node && (
            <div className="flex items-center gap-3 text-xs">
              <span>{node.id} · {node.snapshot}</span>
              <button className={button} onClick={() => { setNode(undefined); setPage(1); }}>
                {t("modeling.enterprise.clear")}
              </button>
            </div>
          )}
          {!loading && result.items.length === 0 && <p className="text-sm">{t("modeling.enterprise.empty")}</p>}
          <div className="space-y-2">
            {(!loading ? result.items : []).map((row) => (
              <article key={row.sequence} className="rounded-md border border-background-200 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <strong className="break-all">
                    {row.nodeId ? `${display(row.data.name ?? row.nodeId)}`
                      : row.source ? `${row.source}${row.target ? ` → ${row.target}` : ""}`
                      : row.members.join(", ")}
                  </strong>
                  <span className="text-xs text-foreground-500">{row.snapshot}</span>
                </div>
                {row.nodeId && <p className="break-all font-mono text-xs">{row.nodeId}</p>}
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer">{t("modeling.enterprise.attributes")}</summary>
                  <dl className="mt-2 grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-2">
                    {Object.entries({
                      ...(typeof row.data.attributes === "object" && row.data.attributes !== null
                        ? row.data.attributes : {}),
                      ...(typeof row.data.properties === "object" && row.data.properties !== null
                        ? row.data.properties : {}),
                      ...Object.fromEntries(Object.entries(row.data).filter(([key]) =>
                        key !== "attributes" && key !== "properties")),
                    }).map(([key, value]) => (
                      <div key={key} className="contents">
                        <dt className="break-all text-foreground-500">{key}</dt>
                        <dd className="break-all whitespace-pre-wrap">{display(value)}</dd>
                      </div>
                    ))}
                  </dl>
                </details>
                {row.kind === "company" && row.nodeId && (
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
                    <button className={button} onClick={() => {
                      setNode({ id: row.nodeId!, snapshot: row.snapshot });
                      setKind("edge"); setKeyword(""); setPage(1);
                    }}>{t("modeling.enterprise.related")}</button>
                    {modelId && (
                      <button className={button} disabled={busy} onClick={() => void act(() =>
                        requestPredictModel({ modelId, companyIds: [row.nodeId!] }),
                      )}>{t("modeling.enterprise.predict")}</button>
                    )}
                    <span>{row.prediction
                      ? `${t("modeling.enterprise.probability")}: ${(row.prediction.probability * 100).toFixed(3)}% · ${t("modeling.enterprise.label")}: ${row.prediction.predictedLabel}`
                      : t("modeling.enterprise.unassessed")}</span>
                    {row.prediction?.uncertainty != null && (
                      <span>{t("modeling.plus.uncertainty")}: {(row.prediction.uncertainty * 100).toFixed(3)}%
                        {" · "}{t("modeling.plus.conflict")}: {((row.prediction.conflict ?? 0) * 100).toFixed(3)}%</span>
                    )}
                  </div>
                )}
              </article>
            ))}
          </div>
          <div className="flex items-center gap-3 text-xs">
            <button className={button} disabled={page === 1 || loading}
              onClick={() => setPage(page - 1)}>{t("modeling.enterprise.previous")}</button>
            <span>{page} / {Math.max(1, Math.ceil(result.total / 20))} · {result.total}</span>
            <button className={button} disabled={page * 20 >= result.total || loading}
              onClick={() => setPage(page + 1)}>{t("modeling.enterprise.next")}</button>
          </div>
        </>
      )}
    </section>
  );
}
