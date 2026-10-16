from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.auth.errors import SESSION_ERRORS
from risk_api.modules.data_prep.api import handler
from risk_api.modules.data_prep.api.schemas import (
    ResponseConversionState,
    ResponseInspectData,
    ResponseListPreparations,
    ResponseModelDefaults,
    ResponsePreparation,
    ResponsePreparationBundle,
    ResponsePreparationDeletion,
    ResponseSuggestMapping,
    ResponseTestModel,
)
from risk_api.modules.data_prep.errors import DATA_PREP_ERRORS
from risk_api.shared.api.envelope import ApiEnvelope
from risk_api.shared.api.response import COMMON_ERROR_RESPONSES

router = APIRouter(route_class=DishkaRoute)
for path, endpoint in (
    ("/conversion/save-plan", handler.save_conversion_plan),
    ("/conversion/trial", handler.trial_conversion),
    ("/conversion/get", handler.get_conversion),
    ("/conversion/import", handler.import_conversion),
):
    router.add_api_route(path, endpoint, methods=["POST"],
                         response_model=ApiEnvelope[ResponseConversionState],
                         responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS)
router.add_api_route(
    "/export", handler.export_preparation, methods=["POST"],
    response_model=ApiEnvelope[ResponsePreparationBundle],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS,
)
router.add_api_route(
    "/list", handler.list_preparations, methods=["POST"],
    response_model=ApiEnvelope[ResponseListPreparations],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS,
)
router.add_api_route(
    "/get", handler.get_preparation, methods=["POST"],
    response_model=ApiEnvelope[ResponsePreparation],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS,
)
router.add_api_route(
    "/save-report", handler.save_report, methods=["POST"],
    response_model=ApiEnvelope[ResponsePreparation],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS,
)
router.add_api_route(
    "/save-mapping", handler.save_mapping, methods=["POST"],
    response_model=ApiEnvelope[ResponsePreparation],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS,
)
router.add_api_route(
    "/model-defaults",
    handler.model_defaults,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseModelDefaults],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS,
)
router.add_api_route(
    "/test-model",
    handler.test_model,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseTestModel],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS,
)
router.add_api_route(
    "/inspect-case", handler.inspect_case, methods=["POST"],
    response_model=ApiEnvelope[ResponsePreparation],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS,
)
router.add_api_route(
    "/inspect",
    handler.inspect_data,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseInspectData],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS,
)
router.add_api_route(
    "/suggest-mapping",
    handler.suggest_mapping,
    methods=["POST"],
    response_model=ApiEnvelope[ResponseSuggestMapping],
    responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS,
)

for delete_path, delete_endpoint in (("/delete-preview", handler.preview_deletion),
                       ("/delete", handler.remove_preparation)):
    router.add_api_route(delete_path, delete_endpoint, methods=["POST"],
                         response_model=ApiEnvelope[ResponsePreparationDeletion],
                         responses=COMMON_ERROR_RESPONSES | SESSION_ERRORS | DATA_PREP_ERRORS)
