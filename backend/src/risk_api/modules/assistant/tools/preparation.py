"""Account-bound preparation tools. Formal import is deliberately HTTP/UI-only."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from strands import tool
from strands.types.tools import AgentTool

from risk_api.errors import AppError
from risk_api.modules.data_prep.conversion import ConversionPlan
from risk_api.modules.data_prep.conversion_service import ConversionService


class SavePlanArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preparation_id: str = Field(description="Owned preparation UUID, without preparation: prefix")
    run_trial: bool = Field(
        default=True,
        description=(
            "Immediately execute a non-importing trial after saving. Default true; set false "
            "only when the user explicitly requests saving a draft without execution."
        ),
    )
    plan: ConversionPlan = Field(
        description=(
            "Use the exact fields read from this case. columns must be an ARRAY, labelMeaning "
            "must be a STRING. Categorical text uses type=text; type=label is only for "
            "enterprise.label, with values mapping source strings to INTEGER 0 or 1."
        )
    )


def preparation_tools(sessions: async_sessionmaker[AsyncSession], owner: str) -> list[AgentTool]:
    async def invoke(
        action: str,
        preparation_id: str,
        plan: dict | None = None,
        task_id: str | None = None,
        run_trial: bool = False,
    ) -> dict:
        plan_saved = False
        try:
            identity = str(UUID(preparation_id))
            task_id = str(UUID(task_id)) if task_id else None
            async with sessions() as session:
                service = ConversionService(session)
                if action == "save":
                    result = await service.save_plan(
                        owner, identity, ConversionPlan.model_validate(plan)
                    )
                    plan_saved = True
                    if run_trial:
                        result = await service.trial(owner, identity)
                elif action == "trial":
                    result = await service.trial(owner, identity)
                else:
                    result = await service.state(owner, identity, task_id)
            return {"status": "success", "content": [{"json": result}]}
        except ValidationError as error:
            details = [
                {"path": "plan." + ".".join(map(str, item["loc"])), "message": item["msg"]}
                for item in error.errors(
                    include_url=False, include_input=False, include_context=False
                )[:8]
            ]
            return {
                "status": "error",
                "content": [
                    {
                        "json": {
                            "code": "DATA_PREP_RULE_INVALID",
                            "message": "可执行规则参数校验未通过，未保存方案。",
                            "errors": details,
                            "hint": "columns须为数组，labelMeaning须为文本；分类用text；"
                            "标签仅映射到enterprise.label，values的值须为整数0或1。"
                            "根据具体路径修正，不能更改业务规则来绕过校验；两次失败后停止重试并说明问题。",
                        }
                    }
                ],
            }
        except ValueError:
            code, message = "DATA_PREP_RULE_INVALID", "准备ID和任务ID须为有效UUID"
        except AppError as error:
            code, message = error.code, error.message
        except Exception:
            code, message = "DATA_PREP_TOOL_FAILED", "转换服务暂不可用，请稍后重试"
        return {
            "status": "error",
            "content": [
                {
                    "json": {
                        "code": code,
                        "message": message,
                        "planSaved": plan_saved,
                    }
                }
            ],
        }

    @tool(inputSchema={"json": SavePlanArguments.model_json_schema()})
    async def preparation_save_plan(
        preparation_id: str,
        plan: dict,
        run_trial: bool = True,
    ) -> dict:
        """Save executable rules and immediately trial them, without formal import.

        First read the exact case using asset_read. Do not guess label meanings or missing
        value rules. This replaces the case's mapping draft and invalidates old trials.
        Does not confirm mapping or import data. Ask the user to inspect rules and results.
        Default run_trial=true returns a real persisted task and verification report;
        blocked means rejected rows exist and import is forbidden. Never invent a trial
        report if task is null. Set run_trial=false only for an explicit save-only request.
        If reading the case fails, do not save a guessed plan. Fix the read first.
        Never claim success unless this tool returns success. After two failed saves,
        stop retrying and explain the precise errors. Do not alter business semantics.

        Args:
            preparation_id: Owned preparation UUID from asset_catalog, without the prefix.
            run_trial: Run verification immediately after saving; defaults to true.
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
        return await invoke("save", preparation_id, plan, run_trial=run_trial)

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
