from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.modeling.api import handler
from risk_api.modules.modeling.api.schemas import (
    ResponseCompleteDatasetUpload,
    ResponseCreateDatasetUpload,
    ResponseGetDataset,
    ResponseGetExperiment,
    ResponseListDatasets,
    ResponseListExperiments,
    ResponseRunExperiment,
)
from risk_api.modules.modeling.errors import (
    CONFIGURATION_INVALID_RESPONSE,
    DATASET_NOT_FOUND_RESPONSE,
    DATASET_NOT_READY_RESPONSE,
    EXPERIMENT_NOT_FOUND_RESPONSE,
    FILE_INVALID_RESPONSE,
    STORAGE_UNAVAILABLE_RESPONSE,
    UPLOAD_INCOMPLETE_RESPONSE,
)
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)

router.add_api_route(
    "/create-upload",
    handler.create_dataset_upload,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseCreateDatasetUpload],
    responses=COMMON_ERROR_RESPONSES
    | SESSION_ERRORS
    | FILE_INVALID_RESPONSE
    | STORAGE_UNAVAILABLE_RESPONSE,
)
router.add_api_route(
    "/complete-upload",
    handler.complete_dataset_upload,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseCompleteDatasetUpload],
    responses=COMMON_ERROR_RESPONSES
    | SESSION_ERRORS
    | DATASET_NOT_FOUND_RESPONSE
    | UPLOAD_INCOMPLETE_RESPONSE
    | FILE_INVALID_RESPONSE
    | STORAGE_UNAVAILABLE_RESPONSE,
)
router.add_api_route(
    "/list-datasets",
    handler.list_datasets,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseListDatasets],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS,
)
router.add_api_route(
    "/get-dataset",
    handler.get_dataset,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseGetDataset],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATASET_NOT_FOUND_RESPONSE,
)
router.add_api_route(
    "/run-experiment",
    handler.run_experiment,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseRunExperiment],
    responses=COMMON_ERROR_RESPONSES
    | SESSION_ERRORS
    | DATASET_NOT_FOUND_RESPONSE
    | DATASET_NOT_READY_RESPONSE
    | UPLOAD_INCOMPLETE_RESPONSE
    | CONFIGURATION_INVALID_RESPONSE
    | STORAGE_UNAVAILABLE_RESPONSE,
)
router.add_api_route(
    "/list-experiments",
    handler.list_experiments,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseListExperiments],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS,
)
router.add_api_route(
    "/get-experiment",
    handler.get_experiment,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseGetExperiment],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | EXPERIMENT_NOT_FOUND_RESPONSE,
)
