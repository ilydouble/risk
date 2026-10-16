"""Account-bound preparation tools. Formal import is deliberately HTTP/UI-only."""

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from strands import tool
from strands.types.tools import AgentTool

from risk_api.errors import AppError
from risk_api.modules.data_prep.conversion import ConversionPlan
from risk_api.modules.data_prep.conversion_service import ConversionService


def preparation_tools(sessions: async_sessionmaker[AsyncSession], owner: str) -> list[AgentTool]:
    async def invoke(
        action: str, preparation_id: str, plan: dict | None = None, task_id: str | None = None
    ) -> dict:
        try:
            identity = str(UUID(preparation_id))
            task_id = str(UUID(task_id)) if task_id else None
            async with sessions() as session:
                service = ConversionService(session)
                if action == "save":
                    result = await service.save_plan(
                        owner, identity, ConversionPlan.model_validate(plan)
                    )
                elif action == "trial":
                    result = await service.trial(owner, identity)
                else:
                    result = await service.state(owner, identity, task_id)
            return {"status": "success", "content": [{"json": result}]}
        except ValidationError:
            code, message = (
                "DATA_PREP_RULE_INVALID",
                (
                    "规则格式无效。须完整覆盖源字段、指定唯一文本enterprise.id；标签须明确values及labelMeaning。"
                    "仅支持text/number/integer/label/ignore和reject/null/fill缺失策略。"
                ),
            )
        except ValueError:
            code, message = "DATA_PREP_RULE_INVALID", "准备ID和任务ID须为有效UUID"
        except AppError as error:
            code, message = error.code, error.message
        except Exception:
            code, message = "DATA_PREP_TOOL_FAILED", "转换服务暂不可用，请稍后重试"
        return {"status": "error", "content": [{"json": {"code": code, "message": message}}]}

    @tool
    async def preparation_save_plan(preparation_id: str, plan: dict) -> dict:
        """Save an executable mapping DRAFT only after discussing uncertain business rules.

        First read the exact case using asset_read. Do not guess label meanings or missing
        value rules. This replaces the case's mapping draft and invalidates old trials.
        Does not confirm mapping or import data. Ask the user to inspect rules and results.

        Args:
            preparation_id: Owned preparation UUID from asset_catalog, without the prefix.
            plan: Object with columns (one per source field), deduplicate ('exact' to drop
                identical raw rows, or 'reject'), labelMeaning (required when mapping labels).
                Each column has field, target, type (text/number/integer/label/ignore),
                missing (reject/null/fill), optional fill, missingValues (explicit list of
                missing tokens; default ['', '未知', 'null', 'none', 'n/a']), and values
                (source-text to 0/1 mapping for label only). Targets: enterprise.id/name/
                community/label, features.<key>, attributes.<key>; ignore has empty target.
                Enterprise ID must be text with missing=reject. Preserve IDs' leading zeros.
                To keep '未知' as a category, exclude it from that column's missingValues.
                No arbitrary code, SQL, aggregation, random split or inferred graph edges.
        """
        return await invoke("save", preparation_id, plan)

    @tool
    async def preparation_trial(preparation_id: str) -> dict:
        """Execute saved fixed conversion rules and verify output, without formal import.

        Returns task ID, before/after samples, input/output/deduplicated/rejected counts,
        bounded errors, hashes and readiness. A blocked task cannot be imported; revise rules
        with user guidance. No raw generated script is executed. Repeated identical trials
        reuse the same task. On success direct the user to the conversion result card to
        inspect and click Confirm import; never claim that a trial already imported data.
        """
        return await invoke("trial", preparation_id)

    @tool
    async def preparation_result(preparation_id: str, task_id: str | None = None) -> dict:
        """Read owned saved rules and latest (or exact) trial result, including import status.

        Indicates whether results still match current rules/mapping/source. Dataset ID is
        only present after the user explicitly imports from the UI. No writes or imports.
        """
        return await invoke("get", preparation_id, task_id=task_id)

    return [preparation_save_plan, preparation_trial, preparation_result]
