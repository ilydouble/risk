import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import * as ModelingApi from "@/entities/modeling/api/modelingApi";
import type {
  ModelingDataset,
  ModelingRun,
  ModelingVersion,
  ModelingEvent,
} from "@/entities/modeling/model/types";
import type {
  ResponsePredictModel,
  ResponseModelingCapabilities,
} from "@/shared/api/generated/schema";
import { handleApiError } from "@/shared/api/http";
import { uploadObject } from "@/shared/api/objectTransfer";

export function useModelingWorkbench() {
  const { t } = useTranslation();
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
  const [predictionResult, setPredictionResult] = useState<{
    modelId: string;
    items: ResponsePredictModel["items"];
  }>({ modelId: "", items: [] });
  const predictions =
    predictionResult.modelId === modelId ? predictionResult.items : [];
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");
  const [eventError, setEventError] = useState("");
  const [busy, setBusy] = useState(false);
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

  const act = async (operation: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await operation();
      await refresh();
    } catch (reason) {
      setError(formatError(reason));
    } finally {
      if (alive.current) setBusy(false);
    }
  };
  const upload = (file: File, name: string) =>
    act(async () => {
      setUploading(true);
      try {
        setUploadPercent(0);
        const ticket = await ModelingApi.requestCreateDatasetUpload({
          name,
          filename: file.name,
          contentType: file.type || "application/zip",
          size: file.size,
        });
        select("dataset", ticket.datasetId);
        await uploadObject(ticket.url, ticket.headers, file, setUploadPercent);
        await ModelingApi.requestCompleteDatasetUpload({
          datasetId: ticket.datasetId,
        });
      } finally {
        setUploading(false);
      }
    });
  const create = (
    id: string,
    name: string,
    epochs: number,
    selectedModel: string,
  ) =>
    act(async () => {
      const response = await ModelingApi.requestCreateRun({
        datasetId: id,
        runnerId: selectedModel,
        name: name.slice(0, 128),
        epochs,
        requestKey: crypto.randomUUID(),
      });
      select("run", response.run.id);
    });
  const cancel = () =>
    act(async () => {
      await ModelingApi.requestCancelRun({ runId });
    });
  const rerun = () =>
    act(async () => {
      const response = await ModelingApi.requestRerun({
        runId,
        requestKey: crypto.randomUUID(),
      });
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
  const predict = (companyIds: string[]) =>
    act(async () => {
      const response = await ModelingApi.requestPredictModel({
        modelId,
        companyIds,
      });
      setPredictionResult({ modelId, items: response.items });
    });
  return {
    capabilities,
    datasets,
    runs,
    models,
    events,
    predictions,
    // Poll recovery must not erase a failed user operation such as an unknown ID.
    error: error || listError || eventError,
    busy,
    loading,
    uploading,
    uploadPercent,
    dataset: datasets.find((item) => item.id === datasetId),
    run: runs.find((item) => item.id === runId),
    model: models.find((item) => item.id === modelId),
    datasetId,
    runId,
    modelId,
    select,
    refresh: () => act(async () => {}),
    upload,
    create,
    cancel,
    rerun,
    publish,
    download,
    predict,
  };
}
