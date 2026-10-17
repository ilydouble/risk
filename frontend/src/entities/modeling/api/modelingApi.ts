import { http } from "@/shared/api/http";
import type {
  RequestModelingCapabilities,
  ResponseModelingCapabilities,
  RequestRunConfiguration,
  ResponseRunConfiguration,
  RequestCreateDatasetUpload,
  ResponseCreateDatasetUpload,
  RequestCompleteDatasetUpload,
  ResponseCompleteDatasetUpload,
  RequestGetDataset,
  ResponseGetDataset,
  RequestListDatasets,
  ResponseListDatasets,
  RequestCreateRun,
  ResponseCreateRun,
  RequestGetRun,
  ResponseGetRun,
  RequestCancelRun,
  ResponseCancelRun,
  RequestRerun,
  ResponseRerun,
  RequestListRuns,
  ResponseListRuns,
  RequestRunEvents,
  ResponseRunEvents,
  RequestPublishModel,
  ResponsePublishModel,
  RequestDeleteModel,
  ResponseDeleteModel,
  RequestGetModel,
  ResponseGetModel,
  RequestListModels,
  ResponseListModels,
  RequestDownloadModel,
  ResponseDownloadModel,
  RequestPredictModel,
  ResponsePredictModel,
} from "@/shared/api/generated/schema";

export const requestCreateDatasetUpload = http.post<
  RequestCreateDatasetUpload,
  ResponseCreateDatasetUpload
>("/modeling/create-upload");
export const requestCompleteDatasetUpload = http.post<
  RequestCompleteDatasetUpload,
  ResponseCompleteDatasetUpload
>("/modeling/complete-upload");
export const requestGetDataset = http.post<
  RequestGetDataset,
  ResponseGetDataset
>("/modeling/get-dataset");
export const requestListDatasets = http.post<
  RequestListDatasets,
  ResponseListDatasets
>("/modeling/list-datasets");
export const requestCreateRun = http.post<RequestCreateRun, ResponseCreateRun>(
  "/modeling/create-run",
);
export const requestGetRun = http.post<RequestGetRun, ResponseGetRun>(
  "/modeling/get-run",
);
export const requestCancelRun = http.post<RequestCancelRun, ResponseCancelRun>(
  "/modeling/cancel-run",
);
export const requestRerun = http.post<RequestRerun, ResponseRerun>(
  "/modeling/rerun",
);
export const requestListRuns = http.post<RequestListRuns, ResponseListRuns>(
  "/modeling/list-runs",
);
export const requestRunEvents = http.post<RequestRunEvents, ResponseRunEvents>(
  "/modeling/run-events",
);
export const requestPublishModel = http.post<
  RequestPublishModel,
  ResponsePublishModel
>("/modeling/publish-model");
export const requestGetModel = http.post<RequestGetModel, ResponseGetModel>(
  "/modeling/get-model",
);
export const requestListModels = http.post<
  RequestListModels,
  ResponseListModels
>("/modeling/list-models");
export const requestDownloadModel = http.post<
  RequestDownloadModel,
  ResponseDownloadModel
>("/modeling/download-model");
export const requestPredictModel = http.post<
  RequestPredictModel,
  ResponsePredictModel
>("/modeling/predict-model");

export const requestCapabilities = http.post<
  RequestModelingCapabilities,
  ResponseModelingCapabilities
>("/modeling/capabilities");

export const requestRunConfiguration = http.post<
  RequestRunConfiguration,
  ResponseRunConfiguration
>("/modeling/run-configuration");

export const requestImportEnterprises = http.post<
  import("@/shared/api/generated/schema").RequestImportEnterprises,
  import("@/shared/api/generated/schema").ResponseImportEnterprises
>("/modeling/import-enterprises");

export const requestListEnterpriseRecords = http.post<
  import("@/shared/api/generated/schema").RequestListEnterpriseRecords,
  import("@/shared/api/generated/schema").ResponseListEnterpriseRecords
>("/modeling/list-enterprise-records");

export const requestEnterpriseSources = http.post<
  import("@/shared/api/generated/schema").RequestEnterpriseSources,
  import("@/shared/api/generated/schema").ResponseEnterpriseSources
>("/modeling/enterprise-sources");
export const requestEnterpriseOverview = http.post<
  import("@/shared/api/generated/schema").RequestGetDataset,
  import("@/shared/api/generated/schema").ResponseEnterpriseOverview
>("/modeling/enterprise-overview");
export const requestEnterpriseCompany = http.post<
  import("@/shared/api/generated/schema").RequestEnterpriseCompany,
  import("@/shared/api/generated/schema").ResponseEnterpriseCompany
>("/modeling/enterprise-company");

export const requestDeleteModel = http.post<RequestDeleteModel, ResponseDeleteModel>(
  "/modeling/delete-model",
);

export const requestClearDataset = http.post<
  import("@/shared/api/generated/schema").RequestClearDataset,
  import("@/shared/api/generated/schema").ResponseClearDataset
>("/modeling/clear-dataset");
