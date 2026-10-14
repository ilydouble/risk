import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from risk_api.modules.assistant.api.schemas import RequestDataPrepContext
from risk_api.modules.assistant.assets import AssetRepository, SessionAsset
from risk_api.modules.assistant.runtime import ModelSettings
from risk_api.modules.assistant.tools import data_qa


def browser_assets():
    return [
        SessionAsset("case:sha", "case.csv", "uploaded_case", 12, {"profile": {"rowCount": 12}}),
        SessionAsset("report:sha", "case.csv · 报告", "analysis_report", None,
                     {"sourceAssetId": "case:sha", "report": {"summary": "待核实"}}),
    ]


def test_catalog_keeps_demo_and_browser_assets_when_workbench_is_empty(monkeypatch):
    @asynccontextmanager
    async def sessions():
        yield Mock()

    repository = Mock()
    repository.enterprise_directory = AsyncMock(return_value={
        "id": "enterprise-directory", "rowCount": 8, "scope": "shared_demo",
    })
    repository.datasets = AsyncMock(return_value=[])
    monkeypatch.setattr(data_qa, "AssetRepository", lambda _: repository)
    tools = {tool.tool_name: tool for tool in data_qa.data_qa_tools(
        sessions, "owner-a", Mock(), browser_assets(),
    )}

    async def run():
        result = (await tools["asset_catalog"]())["content"][0]["json"]
        assert [asset["id"] for asset in result["assets"]] == [
            "enterprise-directory", "case:sha", "report:sha",
        ]
        case, report = result["assets"][1:]
        assert case["rowCount"] == 12 and report["rowCount"] is None
        assert case["persistence"] == report["persistence"] == "browser_memory"
        assert not result["truncated"]
        content = (await tools["asset_read"]("report:sha"))["content"][0]["json"]
        assert content["content"]["sourceAssetId"] == "case:sha"
        assert content["content"]["report"]["summary"] == "待核实"

    asyncio.run(run())
    repository.datasets.assert_awaited_once_with("owner-a")


@pytest.mark.parametrize("asset_id", [f"workbench:{uuid4()}", "workbench:invalid", "case:old"])
def test_asset_read_does_not_expose_other_owner_or_expired_assets(monkeypatch, asset_id):
    @asynccontextmanager
    async def sessions():
        yield Mock()

    repository = Mock()
    repository.datasets = AsyncMock(return_value=[])
    monkeypatch.setattr(data_qa, "AssetRepository", lambda _: repository)
    read = next(tool for tool in data_qa.data_qa_tools(sessions, "owner-a", Mock())
                if tool.tool_name == "asset_read")
    result = asyncio.run(read(asset_id))
    assert result["status"] == "error"
    assert result["content"][0]["json"]["code"] == "ASSET_NOT_FOUND"
    if repository.datasets.await_count:
        assert repository.datasets.call_args.args[0] == "owner-a"


def test_dataset_catalog_query_scopes_owner_and_counts_imported_records():
    session = AsyncMock()
    rows = Mock()
    rows.mappings.return_value.all.return_value = []
    session.execute.return_value = rows
    dataset_id = str(uuid4())
    asyncio.run(AssetRepository(session).datasets("owner-a", dataset_id))
    statement = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "workbench_datasets.owner_id =" in str(statement)
    assert "workbench_enterprise_records.dataset_id = workbench_datasets.id" in str(statement)
    assert "owner-a" in statement.params.values() and dataset_id in statement.params.values()


def test_snapshot_participates_in_idempotency_without_persisting_contents():
    first = ModelSettings("url", "model", 1024, "secret", browser_assets())
    second = ModelSettings("url", "model", 1024, "secret", browser_assets()[:1])
    assert first.public()["assetSnapshotHash"] != second.public()["assetSnapshotHash"]
    assert "case.csv" not in str(first.public()) and "secret" not in str(first.public())


def test_browser_snapshot_payload_is_bounded():
    payload = {
        "filename": "case.csv",
        "profile": {"sha256": "sha", "rowCount": 12, "duplicateRows": 0,
                    "fields": [], "sampleRows": []},
    }
    assert RequestDataPrepContext.model_validate(payload).profile.rowCount == 12
    payload["profile"]["sampleRows"] = [{"value": "x" * 150_000}]
    with pytest.raises(ValidationError):
        RequestDataPrepContext.model_validate(payload)
