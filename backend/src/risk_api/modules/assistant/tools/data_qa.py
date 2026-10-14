"""Account-bound, read-only workbench tools with per-call database sessions."""

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from strands import tool
from strands.types.tools import AgentTool

from risk_api.errors import AppError
from risk_api.modules.chat.service import ChatService
from risk_api.modules.data_qa.repository import DataQARepository
from risk_api.modules.data_qa.service import DataQAService


def data_qa_tools(
    sessions: async_sessionmaker[AsyncSession], owner: str, chat: ChatService
) -> list[AgentTool]:
    async def invoke(
        action: Literal["catalog", "ask"],
        question: str = "",
        dataset_id: str | None = None,
        model_id: str | None = None,
    ) -> dict:
        try:
            if action == "ask":
                question = question.strip()
                if not 1 <= len(question) <= 2000:
                    raise ValueError("Invalid question")
                dataset_id = str(UUID(dataset_id)) if dataset_id is not None else None
                model_id = str(UUID(model_id)) if model_id is not None else None
            # Agent tasks outlive HTTP requests; never reuse a request-scoped session.
            async with sessions() as session:
                service = DataQAService(DataQARepository(session), chat)
                result = (
                    await service.catalog(owner)
                    if action == "catalog"
                    else await service.ask(owner, question, dataset_id, model_id)
                )
            return {"status": "success", "content": [{"json": result}]}
        except ValueError:
            code, message = "DATA_QA_ARGUMENT_INVALID", "问题须为1–2000字符，范围ID须为有效UUID"
        except AppError as error:
            code, message = error.code, error.message
        except Exception:
            # Strands otherwise serializes exception strings, including upstream diagnostics.
            code, message = "DATA_QA_TOOL_FAILED", "工作台查询未完成，请稍后重试"
        return {"status": "error", "content": [{"json": {"code": code, "message": message}}]}

    @tool
    async def workbench_catalog() -> dict:
        """List available workbench fields and the current account's datasets and models.

        Use this to resolve dataset/model names to IDs before a scoped query. The list
        may be truncated; never invent IDs or assume it contains every dataset/model.
        """
        return await invoke("catalog")

    @tool
    async def workbench_ask(
        question: str, dataset_id: str | None = None, model_id: str | None = None
    ) -> dict:
        """Query actual saved workbench data using a natural-language question, read-only.

        Supports datasets, training runs, registered models, imports, enterprise records,
        graph record counts and saved predictions. Returns rows, scope warnings, SQL and
        query plan. Does not run training/inference or access uploaded document contents.

        Args:
            question: Self-contained question (1–2000 characters), including all filters
                from follow-up questions. Each call is independent of previous queries.
            dataset_id: Optional dataset UUID from the catalog; omit for all owned datasets.
            model_id: Optional model UUID from the catalog; affects predictions only.
        """
        return await invoke("ask", question, dataset_id, model_id)

    return [workbench_catalog, workbench_ask]
