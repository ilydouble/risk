import { useCallback, useEffect, useMemo, useState } from "react";
import * as ModelingApi from "@/entities/modeling/api/modelingApi";
import type { ModelingDataset, ModelingExperiment } from "@/entities/modeling/model/types";
import { handleApiError } from "@/shared/api/http";

const ERRORS = {
  MODELING_FILE_INVALID: "ZIP 数据包不符合 Bundle v1 契约",
  MODELING_CONFIGURATION_INVALID: "实验配置与数据包能力不匹配",
  MODELING_UPLOAD_INCOMPLETE: "数据包尚未成功上传",
  MODELING_DATASET_NOT_READY: "数据集尚未完成分析",
  MODELING_STORAGE_UNAVAILABLE: "对象存储暂时不可用",
} as const;

type BusyStage = "" | "uploading" | "queueing";
type ModelName =
  | "logistic_regression"
  | "hist_gradient_boosting"
  | "graph_stats_hgb"
  | "gnn_self_only"
  | "gnn_no_hyper"
  | "gnn_full";

export interface RunInput {
  datasetId: string;
  name: string;
  targetName: string;
  featureMode: "recommended" | "manual";
  featureColumns: string[];
  models: ModelName[];
  useEvents: boolean;
  useRelations: boolean;
  useHyperedges: boolean;
  enableGnnAblations: boolean;
  seed: number;
}

const isActive = (status: string) => ["pending_upload", "queued", "running"].includes(status);

export function useModelingWorkbench() {
  const [datasets, setDatasets] = useState<ModelingDataset[]>([]);
  const [experiments, setExperiments] = useState<ModelingExperiment[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [selectedExperimentId, setSelectedExperimentId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<BusyStage>("");
  const [error, setError] = useState("");

  const refresh = useCallback(async (initial = false) => {
    if (initial) setLoading(true);
    try {
      const [datasetResponse, experimentResponse] = await Promise.all([
        ModelingApi.requestListDatasets({}),
        ModelingApi.requestListExperiments({}),
      ]);
      setDatasets(datasetResponse.items);
      setExperiments(experimentResponse.items);
      setSelectedDatasetId((current) => current || datasetResponse.items[0]?.id || "");
      setSelectedExperimentId((current) => current || experimentResponse.items[0]?.id || "");
    } catch (reason) {
      setError(handleApiError(reason, ERRORS));
    } finally {
      if (initial) setLoading(false);
    }
  }, []);

  const load = useCallback(async () => {
    setError("");
    await refresh(true);
  }, [refresh]);

  useEffect(() => {
    void load();
  }, [load]);

  const hasActiveJobs = useMemo(
    () => datasets.some((item) => isActive(item.status)) || experiments.some((item) => isActive(item.status)),
    [datasets, experiments],
  );

  useEffect(() => {
    if (!hasActiveJobs) return;
    const timer = window.setInterval(() => void refresh(false), 2000);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs, refresh]);

  const upload = useCallback(async (file: File, name: string) => {
    setError("");
    setBusy("uploading");
    try {
      const ticket = await ModelingApi.requestCreateDatasetUpload({
        name,
        filename: file.name,
        contentType: file.type || "application/zip",
        size: file.size,
      });
      const uploaded = await fetch(ticket.url, {
        method: "PUT",
        body: file,
        headers: ticket.headers,
      });
      if (!uploaded.ok) throw new Error(`upload failed: ${uploaded.status}`);
      setBusy("queueing");
      const response = await ModelingApi.requestCompleteDatasetUpload({
        datasetId: ticket.datasetId,
      });
      setDatasets((items) => [response.dataset, ...items.filter((item) => item.id !== response.dataset.id)]);
      setSelectedDatasetId(response.dataset.id);
      setSelectedExperimentId("");
    } catch (reason) {
      setError(handleApiError(reason, ERRORS));
    } finally {
      setBusy("");
    }
  }, []);

  const run = useCallback(async (input: RunInput) => {
    setError("");
    setBusy("queueing");
    try {
      const response = await ModelingApi.requestRunExperiment(input);
      setExperiments((items) => [response.experiment, ...items]);
      setSelectedExperimentId(response.experiment.id);
      return true;
    } catch (reason) {
      setError(handleApiError(reason, ERRORS));
      return false;
    } finally {
      setBusy("");
    }
  }, []);

  const selectedDataset = useMemo(
    () => datasets.find((item) => item.id === selectedDatasetId) ?? null,
    [datasets, selectedDatasetId],
  );
  const selectedExperiment = useMemo(
    () => experiments.find((item) => item.id === selectedExperimentId) ?? null,
    [experiments, selectedExperimentId],
  );

  const selectDataset = useCallback((dataset: ModelingDataset) => {
    setSelectedDatasetId(dataset.id);
    setSelectedExperimentId(
      experiments.find((item) => item.datasetId === dataset.id)?.id ?? "",
    );
  }, [experiments]);

  const selectExperiment = useCallback((experiment: ModelingExperiment) => {
    setSelectedExperimentId(experiment.id);
    setSelectedDatasetId(experiment.datasetId);
  }, []);

  return {
    datasets,
    experiments,
    selectedDataset,
    selectedExperiment,
    loading,
    busy,
    error,
    load,
    upload,
    run,
    selectDataset,
    selectExperiment,
  };
}
