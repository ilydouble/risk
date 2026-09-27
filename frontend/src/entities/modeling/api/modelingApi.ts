import { http } from "@/shared/api/http";
import type {
  RequestCompleteDatasetUpload,
  RequestCreateDatasetUpload,
  RequestGetDataset,
  RequestGetExperiment,
  RequestListDatasets,
  RequestListExperiments,
  RequestRunExperiment,
  ResponseCompleteDatasetUpload,
  ResponseCreateDatasetUpload,
  ResponseGetDataset,
  ResponseGetExperiment,
  ResponseListDatasets,
  ResponseListExperiments,
  ResponseRunExperiment,
} from "@/shared/api/generated/schema";

export const requestCreateDatasetUpload = http.post<
  RequestCreateDatasetUpload,
  ResponseCreateDatasetUpload
>("/modeling/create-upload");
export const requestCompleteDatasetUpload = http.post<
  RequestCompleteDatasetUpload,
  ResponseCompleteDatasetUpload
>("/modeling/complete-upload");
export const requestListDatasets = http.post<RequestListDatasets, ResponseListDatasets>(
  "/modeling/list-datasets",
);
export const requestGetDataset = http.post<RequestGetDataset, ResponseGetDataset>(
  "/modeling/get-dataset",
);
export const requestRunExperiment = http.post<RequestRunExperiment, ResponseRunExperiment>(
  "/modeling/run-experiment",
);
export const requestListExperiments = http.post<
  RequestListExperiments,
  ResponseListExperiments
>("/modeling/list-experiments");
export const requestGetExperiment = http.post<RequestGetExperiment, ResponseGetExperiment>(
  "/modeling/get-experiment",
);
