from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.modeling.api import handler, schemas
from risk_api.modules.modeling.errors import WORKBENCH_ERRORS
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)
router.add_api_route(
    "/create-upload",
    handler.create_upload,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseCreateDatasetUpload],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/complete-upload",
    handler.complete_upload,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseCompleteDatasetUpload],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/get-dataset",
    handler.get_dataset,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseGetDataset],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/create-run",
    handler.create_run,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseCreateRun],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/get-run",
    handler.get_run,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseGetRun],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/cancel-run",
    handler.cancel_run,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseCancelRun],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/rerun",
    handler.rerun,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseRerun],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/run-events",
    handler.run_events,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseRunEvents],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/publish-model",
    handler.publish_model,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponsePublishModel],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/get-model",
    handler.get_model,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseGetModel],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/download-model",
    handler.download_model,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseDownloadModel],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/predict-model",
    handler.predict_model,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponsePredictModel],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/list-datasets",
    handler.list_datasets,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseListDatasets],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/list-runs",
    handler.list_runs,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseListRuns],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
router.add_api_route(
    "/list-models",
    handler.list_models,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseListModels],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)

router.add_api_route(
    "/capabilities",
    handler.capabilities,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseModelingCapabilities],
    responses=COMMON_ERROR_RESPONSES | WORKBENCH_ERRORS,
)
