"""Owner-bound access to the deployed financial model; the agent never supplies features."""

import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from strands import tool
from strands.types.tools import AgentTool

from risk_api.errors import AppError
from risk_api.modules.assistant.protocol.financial import FinancialPredictionReference
from risk_api.modules.decision.client import DecisionClient
from risk_api.modules.decision.repository import DecisionRepository
from risk_api.modules.decision.service import DecisionService
from risk_api.modules.modeling.client import ModelClient

logger = logging.getLogger(__name__)


def financial_risk_tools(
    sessions: async_sessionmaker[AsyncSession], owner: str, client: ModelClient
) -> list[AgentTool]:
    async def invoke(operation: str, **parameters) -> dict:
        try:
            async with sessions() as session:
                service = DecisionService(DecisionRepository(session), DecisionClient(client))
                if operation == "catalog":
                    result = await service.catalog(owner)
                elif operation == "companies":
                    result = await service.companies(owner, **parameters)
                else:
                    saved = await service.predict_company(owner, str(uuid4()), **parameters)
                    source, score = saved.source, saved.result
                    result = FinancialPredictionReference(
                        predictionId=saved.id,
                        modelId=saved.model.id,
                        modelVersion=saved.model.modelVersion,
                        manifestSha256=score.manifestSha256,
                        datasetId=source.datasetId or "",
                        recordId=source.recordId or "",
                        companyId=source.companyId or "",
                        companyName=source.companyName or "",
                        observationMonth=source.observationMonth,
                        eventScore=score.rawProbabilities.event,
                        noEventScore=score.rawProbabilities.no_event,
                        calibratedEventScore=score.calibratedProbabilities.event
                        if score.calibratedProbabilities
                        else None,
                        target=score.target,
                        createdAt=saved.createdAt.isoformat(),
                        featureCount=len(score.providedFeatures),
                        inputSha256=score.stateSha256,
                        limitations=score.limitations,
                    ).model_dump(mode="json")
                # Return typed, serializable data without the stored financial input snapshot.
                return {"status": "success", "content": [{"json": result}]}
        except AppError as error:
            return {
                "status": "error",
                "content": [
                    {
                        "json": {
                            "code": error.code,
                            "message": error.message,
                            "field": error.field,
                            "recovery": "调用 financial_risk_catalog 获取当前可用模型及数据集；"
                            "使用 financial_risk_companies 返回的 recordId，不猜测或补造财务值。",
                        }
                    }
                ],
            }
        except Exception as error:
            logger.error("financial.tool_failed", extra={"error_type": type(error).__name__})
            return {
                "status": "error",
                "content": [
                    {
                        "json": {
                            "code": "DECISION_TOOL_FAILED",
                            "message": "财务预测服务暂不可用，请稍后重试。",
                        }
                    }
                ],
            }

    def dataset_uuid(value: str) -> str:
        try:
            return str(UUID(value))
        except ValueError as error:
            raise AppError(
                422,
                "DECISION_INPUT_INVALID",
                "dataset_id须复制目录中的完整UUID。",
                field="datasetId",
            ) from error

    @tool
    async def financial_risk_catalog() -> dict:
        """Get the deployed financial model and compatible datasets owned by this account.

        This is independent of published RiskGNN graph models. No training or publication is
        needed. If ready is false or no compatible datasets exist, explain the limitation.
        Copy datasetId into the company lookup tool; never substitute another account's data.
        """
        # Convert nested Pydantic values before Strands serializes tool output.
        result = await invoke("catalog")
        if result["status"] == "success":
            payload = result["content"][0]["json"]
            if payload["model"] is not None:
                payload["model"] = payload["model"].model_dump(mode="json")
            payload["datasets"] = [row.model_dump(mode="json") for row in payload["datasets"]]
        return result

    @tool
    async def financial_risk_companies(dataset_id: str, keyword: str = "", page: int = 1) -> dict:
        """Find financial observations by exact company number, name prefix or observation ID.

        dataset_id must come from financial_risk_catalog. Results distinguish companyId from
        recordId and observationMonth. Choose the user's observation period; ask if ambiguous.
        Use the returned recordId for prediction. page is 1-based; each page contains 20 items.
        """
        try:
            if not 1 <= page <= 100000 or len(keyword) > 128:
                raise AppError(422, "DECISION_INPUT_INVALID", "检索参数超出允许范围。")
            result = await invoke(
                "companies",
                dataset_id=dataset_uuid(dataset_id),
                keyword=keyword,
                page=page,
                size=20,
            )
            if result["status"] == "success":
                payload = result["content"][0]["json"]
                payload["items"] = [row.model_dump(mode="json") for row in payload["items"]]
            return result
        except AppError as error:
            return {
                "status": "error",
                "content": [
                    {
                        "json": {
                            "code": error.code,
                            "message": error.message,
                            "field": error.field,
                        }
                    }
                ],
            }

    @tool
    async def predict_company_financial_risk(dataset_id: str, record_id: str) -> dict:
        """Compute and persist a financial score using the deployed UK Qwen3-0.6B LoRA model.

        First use financial_risk_catalog and financial_risk_companies. Copy datasetId and
        recordId exactly; recordId identifies a dated observation, not just a company number.
        The server reads features; never invent or supply missing financial values. Report
        model version, observation month, source and warnings. Neither raw nor calibrated
        scores are UK population default probabilities. No graph explanation, training or
        model switching.
        """
        try:
            if not record_id.strip() or len(record_id) > 512:
                raise AppError(422, "DECISION_INPUT_INVALID", "record_id须为有效观测记录ID。")
            return await invoke("predict", dataset_id=dataset_uuid(dataset_id), record_id=record_id)
        except AppError as error:
            return {
                "status": "error",
                "content": [
                    {
                        "json": {
                            "code": error.code,
                            "message": error.message,
                            "field": error.field,
                        }
                    }
                ],
            }

    return [financial_risk_catalog, financial_risk_companies, predict_company_financial_risk]
