"""Owner-bound inference tools; no publication, training or arbitrary model execution."""

from urllib.parse import quote
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from strands import tool
from strands.types.tools import AgentTool

from risk_api.errors import AppError
from risk_api.modules.modeling.client import ModelClient
from risk_api.modules.modeling.enterprise_browse import EnterpriseBrowseService
from risk_api.modules.modeling.model_catalog import ModelCatalogService
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.service import ModelingService, ModelingStorage


def enterprise_risk_tools(
    sessions: async_sessionmaker[AsyncSession], owner: str,
    storage: ModelingStorage, client: ModelClient,
) -> list[AgentTool]:
    def failure(code: str, message: str, field: str | None = None) -> dict:
        detail: dict = {"code": code, "message": message, "field": field}
        if code in {"MODEL_INPUT_INVALID", "MODELING_RESOURCE_NOT_FOUND"}:
            detail["recovery"] = (
                "调用 enterprise_risk_catalog()（不传筛选参数）重新获取当前账号目录；"
                "复制 models[].modelId 到 model_id、datasetId 到 dataset_id，不能使用名称或 runId。"
                "目录没有目标时说明不可用，不猜测ID或扩大权限范围。"
            )
        return {"status": "error", "content": [{"json": detail}]}

    def uuid_parameter(value: str, field: str) -> str:
        try:
            return str(UUID(value))
        except ValueError as error:
            raise AppError(
                422, "MODEL_INPUT_INVALID", f"{field} 必须是目录返回的完整 UUID，不能填名称。",
                field=field,
            ) from error

    @tool
    async def enterprise_risk_catalog(
        dataset_id: str | None = None, limit: int = 10, model_id: str | None = None
    ) -> dict:
        """List recent published models newest first, with dataset, time, metrics and example IDs.

        limit defaults to 10 and must be 1–50. The first entry is the latest in this scope.

        model_id must be the exact UUID in models[].modelId, never name, datasetId or runId.
        dataset_id must be the exact datasetId UUID, never the dataset name.
        When the ID is unknown, call this tool with no filters to list available versions.
        Use model_id to inspect a specific version even outside the recent list.
        Resolve the exact model ID before predicting. Completed experiments must be published
        in the UI first. If several models match, ask the user to select; never guess a version.
        """
        try:
            identity = uuid_parameter(dataset_id, "dataset_id") if dataset_id is not None else None
            async with sessions() as session:
                if not 1 <= limit <= 50:
                    raise AppError(
                        422, "MODEL_INPUT_INVALID", "limit须为1至50的整数。", field="limit"
                    )
                modeling = ModelingService(ModelingRepository(session), storage, client)
                result = await ModelCatalogService(modeling).list(
                    owner, identity, limit,
                    uuid_parameter(model_id, "model_id") if model_id is not None else None,
                )
            return {"status": "success", "content": [{"json": result}]}
        except AppError as error:
            return failure(error.code, error.message, error.field)
        except Exception:
            return failure("MODELING_TOOL_FAILED", "模型目录暂不可用，请稍后重试。")

    @tool
    async def enterprise_risk_predict(model_id: str, company_id: str) -> dict:
        """Compute and save one enterprise's prediction with a reproducible sensitivity explanation.

        Copy models[].modelId UUID from enterprise_risk_catalog into model_id (not name/runId).
        Use an exact enterprise ID from
        its dataset. Only graph-bound enterprises are supported. No training or publication.
        Report model warnings and label meaning, never call the score a future default probability.
        Delta is score minus score with one feature replaced by the training median. It is not
        SHAP, not causal, and deltas cannot be summed. Relations are factual evidence only.
        """
        try:
            identity = uuid_parameter(model_id, "model_id")
            if not company_id.strip() or len(company_id) > 256:
                raise AppError(422, "MODEL_INPUT_INVALID", "company_id须为1至256字符的原始企业ID。",
                               field="company_id")
            async with sessions() as session:
                modeling = ModelingService(ModelingRepository(session), storage, client)
                version = await modeling.repository.version(owner, identity)
                run = await modeling.repository.run(owner, version.run_id)
                explain = version.artifact.get("profile", {}).get("algorithm") == "RiskGNN+"
                result = await modeling.predict(owner, identity, [company_id], "", explain=explain)
                result.update({
                    "datasetId": run.dataset_id,
                    "modelId": identity, "modelName": version.name,
                    "target": version.artifact.get("profile", {}).get("target"),
                    "testMetrics": version.artifact.get("report", {}).get("metrics", {}),
                    "explanationAvailable": explain,
                    "warning": "分类分数未经校准，不是未来违约概率；无解释时不得编造特征贡献。",
                    "companyUrl": (f"/company/{run.dataset_id}/{quote(company_id, safe='')}"
                                   f"?model={identity}"),
                    "evidence": None,
                })
                try:
                    detail = await EnterpriseBrowseService(modeling).company(
                        owner, run.dataset_id, company_id, identity
                    )
                    result["evidence"] = {
                        "company": detail["company"], "provenance": detail["provenance"],
                        "relations": {kind: {
                            "total": page["total"],
                            "items": [{
                                "sequence": row["sequence"], "source": row["source"],
                                "target": row["target"], "memberCount": len(row["members"]),
                                "members": row["members"][:20],
                                "relation": row["data"].get("relation"),
                                "kind": row["data"].get("kind"),
                                "sourceRecord": row["data"].get("sourceRecord"),
                            } for row in page["items"][:5]],
                        } for kind, page in detail["related"].items()},
                        "note": "每类关系最多5条、每组最多20名成员，其余见企业详情；"
                                "关系存在不等于风险贡献。",
                    }
                except AppError as error:
                    if error.code != "MODELING_COMPANY_NOT_FOUND":
                        raise
                    result["evidenceWarning"] = "企业原始记录尚未导入，暂无属性及关系来源可追溯。"
            return {"status": "success", "content": [{"json": result}]}
        except AppError as error:
            return failure(error.code, error.message, error.field)
        except Exception:
            return failure("MODELING_TOOL_FAILED", "预测解释暂不可用，未获得结果；请稍后重试。")

    @tool
    async def enterprise_risk_companies(model_id: str, keyword: str = "", page: int = 1) -> dict:
        """Find enterprises by name or original ID in the published model's dataset.

        Copy models[].modelId UUID from enterprise_risk_catalog into model_id, not name,
        datasetId or runId. If missing, call enterprise_risk_catalog() with no filters first.
        Return exact company IDs, 20 per page.
        An empty keyword lists candidates; multiple matches require user clarification.
        Dataset membership does not guarantee inclusion in a subset-trained model's graph.
        Never substitute shared demo company IDs or invent IDs.
        """
        try:
            identity = uuid_parameter(model_id, "model_id")
            if len(keyword) > 256:
                raise AppError(
                    422, "MODEL_INPUT_INVALID", "keyword不能超过256字符。", field="keyword"
                )
            if not 1 <= page <= 10000:
                raise AppError(422, "MODEL_INPUT_INVALID", "page须为1至10000的整数。", field="page")
            async with sessions() as session:
                modeling = ModelingService(ModelingRepository(session), storage, client)
                result = await ModelCatalogService(modeling).companies(
                    owner, identity, keyword.strip(), page
                )
            return {"status": "success", "content": [{"json": result}]}
        except AppError as error:
            return failure(error.code, error.message, error.field)
        except Exception:
            return failure("MODELING_TOOL_FAILED", "模型企业目录暂不可用，请稍后重试。")

    return [enterprise_risk_catalog, enterprise_risk_predict, enterprise_risk_companies]
