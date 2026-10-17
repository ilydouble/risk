import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuthUser } from "@/features/auth/model/AuthContext";
import * as ModelingApi from "@/entities/modeling/api/modelingApi";
import type {
  ModelingDataset,
  ModelingRun,
  ModelingVersion,
  ModelingEvent,
} from "@/entities/modeling/model/types";
import type {
  ResponseModelingCapabilities,
} from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { uploadDatasetPackage } from "@/features/dataset-delivery/lib/upload";

export function useModelingWorkbench() {
  const { t } = useTranslation();
  const user = useAuthUser();
  const [params, setParams] = useSearchParams();
  const datasetId = params.get("dataset") ?? "";
  const runId = params.get("run") ?? "";
  const modelId = params.get("model") ?? "";
  const [capabilities, setCapabilities] = useState<
    ResponseModelingCapabilities["items"]
  >([]);
  const [datasets, setDatasets] = useState<ModelingDataset[]>([]);
  const [runs, setRuns] = useState<ModelingRun[]>([]);
  const [models, setModels] = useState<ModelingVersion[]>([]);
  const [events, setEvents] = useState<ModelingEvent[]>([]);
  const [copiedRun, setCopiedRun] = useState<ModelingRun | null>(null);
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");
  const [eventError, setEventError] = useState("");
  const [busy, setBusy] = useState(false);
  const operationPending = useRef(false);
  const submissionKey = useRef({ signature: "", key: "" });
  const [submitting, setSubmitting] = useState(false);
  const [selectedRun, setSelectedRun] = useState<ModelingRun>();
  const [runCheckedAt, setRunCheckedAt] = useState<number>();
  const [runStatusError, setRunStatusError] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState(0);
  const eventCursor = useRef({ runId: "", after: 0 });
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const formatError = useCallback(
    (reason: unknown) =>
      handleApiError(reason, {
        MODEL_SERVICE_UNAVAILABLE: t("modeling.errors.unavailable"),
        MODELING_DATASET_NOT_READY: t("modeling.errors.notReady"),
        MODELING_STATE_INVALID: t("modeling.errors.state"),
        MODEL_RESOURCE_NOT_FOUND: t("modeling.errors.missing"),
        MODELING_FILE_INVALID: t("modeling.errors.file"),
        MODELING_MODEL_INCOMPATIBLE: t("modeling.errors.incompatible"),
        MODELING_CONFIG_STALE: t("modeling.errors.staleConfig"),
        EXECUTION_PARAMETERS_INVALID: t("modeling.errors.parameters"),
      }),
    [t],
  );
  const select = useCallback(
    (kind: string, id: string) => {
      setParams((previous) => {
        const next = new URLSearchParams(previous);
        next.set(kind, id);
        next.set("tab", kind);
        return next;
      });
    },
    [setParams],
  );

  const refresh = useCallback(async () => {
    const [data, experiments, versions, catalog] = await Promise.all([
      ModelingApi.requestListDatasets({
        pagination: { page: 1, pageSize: 100 },
      }),
      ModelingApi.requestListRuns({ pagination: { page: 1, pageSize: 100 } }),
      ModelingApi.requestListModels({ pagination: { page: 1, pageSize: 100 } }),
      ModelingApi.requestCapabilities({}),
    ]);
    if (alive.current) {
      setCapabilities(catalog.items);
      setDatasets(data.items);
      setRuns(experiments.items);
      setModels(versions.items);
    }
  }, []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        await refresh();
        if (active) setListError("");
      } catch (reason) {
        if (active) setListError(formatError(reason));
      } finally {
        if (active) {
          setLoading(false);
          timer = setTimeout(() => void poll(), 2000);
        }
      }
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [refresh, formatError]);
  useEffect(() => {
    eventCursor.current = { runId, after: 0 };
    setEvents([]);
    setEventError("");
    if (!runId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await ModelingApi.requestRunEvents({
          runId,
          after: eventCursor.current.after,
        });
        if (!active) return;
        setEventError("");
        if (result.items.length) {
          eventCursor.current.after = result.items.at(-1)!.sequence;
          setEvents((previous) => [...previous, ...result.items].slice(-2000));
        }
      } catch (reason) {
        if (active) setEventError(formatError(reason));
      } finally {
        if (active) timer = setTimeout(() => void poll(), 2000);
      }
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [runId, formatError]);

  useEffect(() => {
    if (!runId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const response = await ModelingApi.requestGetRun({ runId });
        if (!active) return;
        setSelectedRun(response.run);
        setRunCheckedAt(Date.now());
        setRunStatusError("");
      } catch (reason) {
        if (active) setRunStatusError(formatError(reason));
      } finally {
        if (active) timer = setTimeout(() => void poll(), 2000);
      }
    };
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [runId, formatError]);

  const act = async (operation: () => Promise<void>) => {
    if (operationPending.current) return;
    operationPending.current = true;
    setBusy(true);
    setError("");
    try {
      await operation();
      await refresh();
    } catch (reason) {
      setError(formatError(reason));
    } finally {
      operationPending.current = false;
      if (alive.current) setBusy(false);
    }
  };
  const upload = (file: File, name: string) =>
    act(async () => {
      setUploading(true);
      try {
        setUploadPercent(0);
        await uploadDatasetPackage(file, name, {
          progress: setUploadPercent,
          created: id => select("dataset", id),
        });
      } finally {
        setUploading(false);
      }
    });
  const create = (
    id: string,
    name: string,
    parameters: Record<string, unknown>,
    configurationDigest: string,
  ) =>
    act(async () => {
      setSubmitting(true);
      try {
        const signature = JSON.stringify([id, name, parameters, configurationDigest]);
        // A lost response must retry the accepted operation instead of creating another run.
        if (submissionKey.current.signature !== signature) {
          submissionKey.current = { signature, key: crypto.randomUUID() };
        }
        const response = await ModelingApi.requestCreateRun({
          datasetId: id,
          runnerId: "riskgnn",
          name: name.slice(0, 128),
          parameters,
          configurationDigest,
          requestKey: submissionKey.current.key,
        });
        submissionKey.current = { signature: "", key: "" };
        setSelectedRun(response.run);
        setRunCheckedAt(undefined);
        setRuns(previous => [response.run, ...previous.filter(item => item.id !== response.run.id)]);
        setRunStatusError("");
        select("run", response.run.id);
        setCopiedRun(null);
      } finally {
        setSubmitting(false);
      }
    });
  const cancel = () =>
    act(async () => {
      await ModelingApi.requestCancelRun({ runId });
    });
  const copyRun = () => {
    const previous = runs.find((item) => item.id === runId);
    if (!previous?.configuration) return;
    setCopiedRun(previous);
    select("dataset", previous.datasetId);
  };
  const rerun = () =>
    act(async () => {
      const response = await ModelingApi.requestRerun({
        runId,
        requestKey: crypto.randomUUID(),
      });
      setSelectedRun(response.run);
      setRunCheckedAt(undefined);
      setRuns(previous => [response.run, ...previous.filter(item => item.id !== response.run.id)]);
      select("run", response.run.id);
    });
  const publish = (name: string) =>
    act(async () => {
      const response = await ModelingApi.requestPublishModel({ runId, name });
      select("model", response.model.id);
    });
  const download = () =>
    act(async () => {
      const response = await ModelingApi.requestDownloadModel({ modelId });
      const link = document.createElement("a");
      link.href = response.url;
      link.download = "model.zip";
      link.click();
    });
  return {
    capabilities,
    datasets,
    runs,
    models,
    events,
    // Poll recovery must not erase a failed user operation such as an unknown ID.
    error: error || listError || eventError,
    busy,
    submitting,
    runCheckedAt: selectedRun?.id === runId ? runCheckedAt : undefined,
    runStatusError,
    loading,
    uploading,
    uploadPercent,
    dataset: datasets.find((item) => item.id === datasetId),
    run: selectedRun?.id === runId ? selectedRun : runs.find((item) => item.id === runId),
    model: models.find((item) => item.id === modelId),
    datasetId,
    runId,
    modelId,
    select,
    refresh: () => act(async () => {}),
    datasetCleared: () => {
      try {
        const key = `risk:enterprise-source:${user?.userId ?? ""}`;
        const saved = JSON.parse(localStorage.getItem(key) ?? "null");
        if (saved?.dataset === datasetId) localStorage.removeItem(key);
      } catch { /* Selection cleanup must work when browser storage is unavailable. */ }
      setDatasets(previous => previous.filter(item => item.id !== datasetId));
      setCopiedRun(null);
      setParams(previous => {
        const next = new URLSearchParams(previous);
        for (const key of ["dataset", "run", "model"]) next.delete(key);
        next.set("tab", "dataset");
        return next;
      });
      void act(async () => {});
    },
    upload,
    create,
    cancel,
    rerun,
    copyRun,
    copiedRun,
    publish,
    download,
  };
}
