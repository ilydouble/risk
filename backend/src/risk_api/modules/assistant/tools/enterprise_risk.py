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
    def failure(code: str, message: str) -> dict:
        return {"status": "error", "content": [{"json": {"code": code, "message": message}}]}

    @tool
    async def enterprise_risk_catalog(
        dataset_id: str | None = None, limit: int = 10, model_id: str | None = None
    ) -> dict:
        """List recent published models newest first, with dataset, time, metrics and example IDs.

        limit defaults to 10 and must be 1–50. The first entry is the latest in this scope.

        Use model_id to inspect a specific version even outside the recent list.
        Resolve the exact model ID before predicting. Completed experiments must be published
        in the UI first. If several models match, ask the user to select; never guess a version.
        """
        try:
            identity = str(UUID(dataset_id)) if dataset_id else None
            async with sessions() as session:
                if not 1 <= limit <= 50:
                    raise ValueError("Invalid limit")
                modeling = ModelingService(ModelingRepository(session), storage, client)
                result = await ModelCatalogService(modeling).list(
                    owner, identity, limit, str(UUID(model_id)) if model_id else None
                )
            return {"status": "success", "content": [{"json": result}]}
        except ValueError:
            return failure("MODEL_INPUT_INVALID", "dataset_id须为有效UUID，limit须在1至50之间。")
        except AppError as error:
            return failure(error.code, error.message)
        except Exception:
            return failure("MODELING_TOOL_FAILED", "模型目录暂不可用，请稍后重试。")

    @tool
    async def enterprise_risk_predict(model_id: str, company_id: str) -> dict:
        """Compute and save one enterprise's prediction with a reproducible sensitivity explanation.

        Use a published model ID from enterprise_risk_catalog and an exact enterprise ID from
        its dataset. Only graph-bound enterprises are supported. No training or publication.
        Report model warnings and label meaning, never call the score a future default probability.
        Delta is score minus score with one feature replaced by the training median. It is not
        SHAP, not causal, and deltas cannot be summed. Relations are factual evidence only.
        """
        try:
            identity = str(UUID(model_id))
            if not company_id.strip() or len(company_id) > 256:
                raise ValueError("Invalid company ID")
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
        except ValueError:
            return failure("MODEL_INPUT_INVALID", "模型ID须为UUID，企业ID须为原始字符串标识。")
        except AppError as error:
            return failure(error.code, error.message)
        except Exception:
            return failure("MODELING_TOOL_FAILED", "预测解释暂不可用，未获得结果；请稍后重试。")

    @tool
    async def enterprise_risk_companies(model_id: str, keyword: str = "", page: int = 1) -> dict:
        """Find enterprises by name or original ID in the published model's dataset.

        Use catalog to resolve model_id first. Return exact company IDs, 20 per page.
        An empty keyword lists candidates; multiple matches require user clarification.
        Dataset membership does not guarantee inclusion in a subset-trained model's graph.
        Never substitute shared demo company IDs or invent IDs.
        """
        try:
            identity = str(UUID(model_id))
            if len(keyword) > 256 or not 1 <= page <= 10000:
                raise ValueError("Invalid search")
            async with sessions() as session:
                modeling = ModelingService(ModelingRepository(session), storage, client)
                result = await ModelCatalogService(modeling).companies(
                    owner, identity, keyword.strip(), page
                )
            return {"status": "success", "content": [{"json": result}]}
        except ValueError:
            return failure(
                "MODEL_INPUT_INVALID", "模型ID须为UUID，关键词不超过256字符，页码为1至10000。"
            )
        except AppError as error:
            return failure(error.code, error.message)
        except Exception:
            return failure("MODELING_TOOL_FAILED", "模型企业目录暂不可用，请稍后重试。")

    return [enterprise_risk_catalog, enterprise_risk_predict, enterprise_risk_companies]
