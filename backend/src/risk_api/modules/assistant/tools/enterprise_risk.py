"""Owner-bound inference tools; no publication, training or arbitrary model execution."""

from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from strands import tool
from strands.types.tools import AgentTool

from risk_api.errors import AppError
from risk_api.modules.modeling.client import ModelClient
from risk_api.modules.modeling.enterprise_browse import EnterpriseBrowseService
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.service import ModelingService, ModelingStorage
from risk_api.modules.modeling.workbench_model import ModelVersion, Run


def enterprise_risk_tools(
    sessions: async_sessionmaker[AsyncSession], owner: str,
    storage: ModelingStorage, client: ModelClient,
) -> list[AgentTool]:
    def failure(code: str, message: str) -> dict:
        return {"status": "error", "content": [{"json": {"code": code, "message": message}}]}

    @tool
    async def enterprise_risk_catalog(dataset_id: str | None = None) -> dict:
        """List up to 50 published models owned by this account, with dataset IDs and test metrics.

        Resolve the exact model ID before predicting. Completed experiments must be published
        in the UI first. If several models match, ask the user to select; never guess a version.
        """
        try:
            identity = str(UUID(dataset_id)) if dataset_id else None
            async with sessions() as session:
                if identity:
                    await ModelingRepository(session).dataset(owner, identity)
                query = select(ModelVersion, Run.dataset_id).join(
                    Run, Run.id == ModelVersion.run_id
                )
                query = query.where(
                    ModelVersion.owner_id == owner, Run.owner_id == owner,
                    ModelVersion.protocol_generation == 2, Run.protocol_generation == 2,
                )
                if identity:
                    query = query.where(Run.dataset_id == identity)
                rows = list((await session.execute(
                    query.order_by(ModelVersion.created_at.desc(), ModelVersion.id).limit(51)
                )).all())
                result = {"models": [{
                    "modelId": model.id, "name": model.name, "datasetId": dataset,
                    "target": model.artifact.get("profile", {}).get("target"),
                    "metrics": model.artifact.get("report", {}).get("metrics", {}),
                } for model, dataset in rows[:50]], "truncated": len(rows) > 50}
            return {"status": "success", "content": [{"json": result}]}
        except ValueError:
            return failure("MODEL_INPUT_INVALID", "dataset_id须为有效UUID。")
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
                result = await modeling.predict(owner, identity, [company_id], "", explain=True)
                result.update({
                    "datasetId": run.dataset_id,
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

    return [enterprise_risk_catalog, enterprise_risk_predict]
