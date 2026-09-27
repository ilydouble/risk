import { useCallback, useEffect, useState } from "react";
import * as ModelingApi from "@/entities/modeling/api/modelingApi";
import type { ModelingDataset, ModelingExperiment } from "@/entities/modeling/model/types";
import { handleApiError } from "@/shared/api/http";

const ERRORS = {
  MODELING_FILE_INVALID: "CSV 文件不符合分析要求",
  MODELING_CONFIGURATION_INVALID: "目标或特征配置无法完成训练",
  MODELING_UPLOAD_INCOMPLETE: "文件尚未成功上传",
  MODELING_DATASET_NOT_READY: "数据集尚未完成分析",
  MODELING_STORAGE_UNAVAILABLE: "对象存储暂时不可用",
} as const;

type BusyStage = "" | "uploading" | "analyzing" | "training";

interface RunInput {
  datasetId: string;
  name: string;
  targetColumn: string;
  positiveValue: string;
  featureColumns: string[];
  seed: number;
}

export function useModelingWorkbench() {
  const [datasets, setDatasets] = useState<ModelingDataset[]>([]);
  const [experiments, setExperiments] = useState<ModelingExperiment[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<ModelingDataset | null>(null);
  const [selectedExperiment, setSelectedExperiment] = useState<ModelingExperiment | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<BusyStage>("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [datasetResponse, experimentResponse] = await Promise.all([
        ModelingApi.requestListDatasets({}),
        ModelingApi.requestListExperiments({}),
      ]);
      setDatasets(datasetResponse.items);
      setExperiments(experimentResponse.items);
      setSelectedDataset((current) => current ?? datasetResponse.items[0] ?? null);
      setSelectedExperiment((current) => current ?? experimentResponse.items[0] ?? null);
    } catch (reason) {
      setError(handleApiError(reason, ERRORS));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const upload = useCallback(async (file: File, name: string) => {
    setError("");
    setBusy("uploading");
    try {
      const ticket = await ModelingApi.requestCreateDatasetUpload({
        name,
        filename: file.name,
        contentType: file.type || "text/csv",
        size: file.size,
      });
      const uploaded = await fetch(ticket.url, {
        method: "PUT",
        body: file,
        headers: ticket.headers,
      });
      if (!uploaded.ok) throw new Error(`upload failed: ${uploaded.status}`);
      setBusy("analyzing");
      const response = await ModelingApi.requestCompleteDatasetUpload({
        datasetId: ticket.datasetId,
      });
      setDatasets((items) => [response.dataset, ...items]);
      setSelectedDataset(response.dataset);
      setSelectedExperiment(null);
    } catch (reason) {
      setError(handleApiError(reason, ERRORS));
    } finally {
      setBusy("");
    }
  }, []);

  const run = useCallback(async (input: RunInput) => {
    setError("");
    setBusy("training");
    try {
      const response = await ModelingApi.requestRunExperiment({
        ...input,
        modelType: "logistic_regression",
      });
      setExperiments((items) => [response.experiment, ...items]);
      setSelectedExperiment(response.experiment);
    } catch (reason) {
      setError(handleApiError(reason, ERRORS));
    } finally {
      setBusy("");
    }
  }, []);

  const selectDataset = useCallback((dataset: ModelingDataset) => {
    setSelectedDataset(dataset);
    setSelectedExperiment(experiments.find((item) => item.datasetId === dataset.id) ?? null);
  }, [experiments]);

  const selectExperiment = useCallback((experiment: ModelingExperiment) => {
    setSelectedExperiment(experiment);
    setSelectedDataset((current) =>
      datasets.find((item) => item.id === experiment.datasetId) ?? current,
    );
  }, [datasets]);

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
