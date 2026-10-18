import hashlib
import json

from risk_api.errors import AppError
from risk_api.modules.decision.contracts import FinancialModelResult, FinancialModelStatus
from risk_api.modules.modeling.client import ModelClient


class DecisionClient:
    def __init__(self, client: ModelClient):
        self.client = client

    async def status(self) -> FinancialModelStatus:
        try:
            return FinancialModelStatus.model_validate(
                await self.client.call("decision/status", {})
            )
        except ValueError as error:
            raise AppError(503, "DECISION_PROTOCOL_INVALID", "财务模型服务协议不兼容。") from error

    async def predict(self, body: dict, *, record: bool) -> FinancialModelResult:
        try:
            result = FinancialModelResult.model_validate(
                await self.client.call(
                    "decision/predict-record" if record else "decision/predict",
                    body,
                )
            )
            model, prediction = result.model, result.prediction
            state = json.dumps(prediction.inputSnapshot, separators=(",", ":"), allow_nan=False)
            if (
                prediction.manifestSha256 != body.get("expectedManifestSha256")
                or prediction.manifestSha256 != model.manifestSha256
                or prediction.modelVersion != model.modelVersion
                or prediction.inputContractSha256 != model.inputContractSha256
                or prediction.expectedBaseRevision != model.baseRevision
                or prediction.target != model.target
                or prediction.stateSha256 != hashlib.sha256(state.encode()).hexdigest()
                or model.labels != ["no_event", "event"]
                or (prediction.calibratedProbabilities is not None) != model.calibrationAvailable
            ):
                raise ValueError("Model result provenance mismatch")
            return result
        except ValueError as error:
            raise AppError(
                503, "DECISION_PROTOCOL_INVALID", "财务模型返回的结果不一致。"
            ) from error
