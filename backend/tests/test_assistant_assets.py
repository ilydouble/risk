import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from risk_api.modules.assistant.assets import AssetRepository
from risk_api.modules.assistant.tools import data_qa


def test_catalog_keeps_demo_assets_when_workbench_is_empty(monkeypatch):
    @asynccontextmanager
    async def sessions():
        yield Mock()

    repository = Mock()
    repository.enterprise_directory = AsyncMock(return_value={
        "id": "enterprise-directory", "rowCount": 8, "scope": "shared_demo",
    })
    repository.datasets = AsyncMock(return_value=[])
    repository.singapore_snapshot = AsyncMock(return_value=None)
    monkeypatch.setattr(data_qa, "AssetRepository", lambda _: repository)
    tools = {tool.tool_name: tool for tool in data_qa.data_qa_tools(
        sessions, "owner-a", Mock(),
    )}

    async def run():
        result = (await tools["asset_catalog"]())["content"][0]["json"]
        assert [asset["id"] for asset in result["assets"]] == [
            "enterprise-directory",
        ]
        assert not result["truncated"]
        assert result["sourceGroups"]["shared_demo"] == ["enterprise-directory"]
        assert result["sourceGroups"]["current_account"] == []
        assert set(result["sourceGroups"]) == {"shared_demo", "current_account"}
        repository.datasets.return_value = [{
            "id": "workbench:owned", "scope": "current_account", "rowCount": 5,
        }]
        repository.singapore_snapshot.return_value = {"asset": {
            "id": "singapore-snapshot:sg", "scope": "shared_demo", "rowCount": 2_110_000,
        }}
        mixed = (await tools["asset_catalog"]())["content"][0]["json"]
        assert mixed["sourceGroups"]["current_account"] == ["workbench:owned"]
        assert mixed["sourceGroups"]["shared_demo"] == [
            "enterprise-directory", "singapore-snapshot:sg",
        ]
        assert "totalRows" not in mixed

    asyncio.run(run())
    assert all(call.args == ("owner-a",) for call in repository.datasets.await_args_list)


@pytest.mark.parametrize("asset_id", [
    f"workbench:{uuid4()}", "workbench:invalid", "case:old",
    f"preparation:{uuid4()}", f"preparation-report:{uuid4()}",
])
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


def test_singapore_aggregate_and_searchable_sample_are_distinct(monkeypatch):
    from types import SimpleNamespace

    from risk_api.modules.assistant import assets

    snapshot = SimpleNamespace(id="sg-snapshot", source_sha256="sha", payload={
        "dataset": {"id": "sg", "country": "SG"}, "stats": {"companyCount": 2_110_000},
        "sampling": {"method": "stratified"}, "sampleCompanies": [{"companyId": "001"}],
    })
    repository = Mock()
    repository.latest = AsyncMock(return_value=snapshot)
    monkeypatch.setattr(assets, "OverviewRepository", lambda session: repository)

    async def run():
        service = AssetRepository(Mock())
        result = await service.singapore_snapshot()
        asset = result["asset"]
        assert asset["scope"] == "shared_demo" and asset["source"] == "singapore_demo"
        assert asset["rowCount"] == 2_110_000 and asset["searchableSampleCount"] == 1
        assert result["rows"] == [{"companyId": "001"}]
        assert "实时模型预测" in " ".join(asset["warnings"])
        assert await service.singapore_snapshot("other-snapshot") is None
    asyncio.run(run())
