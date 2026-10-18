from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from risk_api.modules.decision.api import handler, schemas
from risk_api.modules.decision.errors import DECISION_ERRORS
from risk_api.shared.api.envelope import ApiEnvelope

router = APIRouter(route_class=DishkaRoute, responses=DECISION_ERRORS)
router.add_api_route(
    "/catalog",
    handler.catalog,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseFinancialCatalog],
)
router.add_api_route(
    "/companies",
    handler.companies,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseFinancialCompanies],
)
router.add_api_route(
    "/predict",
    handler.predict,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponsePredictFinancialCompany],
)
router.add_api_route(
    "/preview-input",
    handler.preview,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponsePreviewFinancialInput],
)
router.add_api_route(
    "/get-prediction",
    handler.get,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseGetFinancialPrediction],
)
router.add_api_route(
    "/list-predictions",
    handler.history,
    methods=["POST"],
    response_model=ApiEnvelope[schemas.ResponseListFinancialPredictions],
)
