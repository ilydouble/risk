"""Dataset graph contract across ownership, snapshots and bounded expansion."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from risk_api.errors import AppError
from risk_api.modules.auth.model import User
from risk_api.modules.graph import dataset_service
from risk_api.modules.graph.dataset_service import DatasetGraphService
from risk_api.modules.modeling.workbench_model import Dataset, EnterpriseImport, EnterpriseRecord


def test_dataset_graph_postgres(monkeypatch):
    url = os.getenv("RISK_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RISK_TEST_DATABASE_URL for isolated graph queries")

    async def exercise():
        schema = "test_graph_" + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                for model in (User, Dataset, EnterpriseImport, EnterpriseRecord):
                    await conn.run_sync(model.__table__.create)
            owner, dataset = str(uuid4()), str(uuid4())
            async with sessions() as session:
                session.add(
                    User(id=owner, username="graph", display_name="graph", password_hash="x")
                )
                await session.flush()
                session.add(
                    Dataset(
                        id=dataset,
                        owner_id=owner,
                        name="Dataset graph",
                        filename="x.zip",
                        object_key="x",
                        size=1,
                        content_type="application/zip",
                    )
                )
                await session.flush()
                session.add(
                    EnterpriseImport(dataset_id=dataset, sha256="a" * 64, manifest={}, counts={})
                )
                await session.flush()
                sequence = 0

                def add(
                    kind,
                    *,
                    node=None,
                    source=None,
                    target=None,
                    members=None,
                    snapshot="test",
                    data=None,
                ):
                    nonlocal sequence
                    sequence += 1
                    session.add(
                        EnterpriseRecord(
                            dataset_id=dataset,
                            sequence=sequence,
                            snapshot=snapshot,
                            kind=kind,
                            node_id=node,
                            source=source,
                            target=target,
                            members=members or [],
                            data=data or {},
                        )
                    )

                for name, kind in [
                    ("A", "company"),
                    ("P", "person"),
                    ("B", "company"),
                    ("C", "company"),
                    ("alone", "company"),
                ]:
                    add(kind, node=name, data={"name": name, "attributes": {}})
                add("person", node="P", snapshot="train", data={"name": "must-not-leak"})
                add("company", node="foreign-snapshot", snapshot="train")
                add("edge", source="P", target="foreign-snapshot", snapshot="train")
                add("edge", source="A", target="P", data={"relation": "owns", "weight": 0.5})
                add("edge", source="P", target="A", data={"relation": "reverse"})
                add("edge", source="A", target="P", data={"relation": "parallel"})
                add("edge", source="A", target="A", data={"relation": "self"})
                add("edge", source="P", target="B", data={"relation": "second-hop"})
                add("hyperedge", members=["C", "A"], data={"kind": "group"})
                add("event", source="A", data={"cause": 1, "age_months": 2})
                await session.commit()
                service = DatasetGraphService(session)
                first = await service.get(owner, dataset, "A", 1)
                assert not first["truncated"]
                assert {n["entityId"] for n in first["nodes"] if n["entityId"]} == {"A", "P", "C"}
                assert {n["kind"] for n in first["nodes"]} == {
                    "company",
                    "person",
                    "hyperedge",
                    "event",
                }
                assert len(first["edges"]) == 7
                assert len({e["id"] for e in first["edges"]}) == 7
                assert all(e["data"]["snapshot"] == "test" for e in first["edges"])
                assert "B" in {
                    n["entityId"] for n in (await service.get(owner, dataset, "A", 2))["nodes"]
                }
                assert first == await service.get(owner, dataset, "A", 1)
                second_hop = await service.get(owner, dataset, "A", 2)
                assert "foreign-snapshot" not in {n["entityId"] for n in second_hop["nodes"]}
                other_dataset = str(uuid4())
                session.add(
                    Dataset(
                        id=other_dataset,
                        owner_id=owner,
                        name="Other dataset",
                        filename="other.zip",
                        object_key="other",
                        size=1,
                        content_type="application/zip",
                    )
                )
                await session.flush()
                session.add(
                    EnterpriseImport(
                        dataset_id=other_dataset, sha256="b" * 64, manifest={}, counts={}
                    )
                )
                await session.flush()
                session.add(
                    EnterpriseRecord(
                        dataset_id=other_dataset,
                        sequence=1,
                        snapshot="test",
                        kind="company",
                        node_id="A",
                        members=[],
                        data={"name": "Same ID, another company"},
                    )
                )
                await session.commit()
                other = await service.get(owner, other_dataset, "A", 1)
                assert other["nodes"][0]["label"] == "Same ID, another company"
                assert other["datasetId"] == other_dataset and not other["edges"]
                isolated = await service.get(owner, dataset, "alone", 3)
                assert len(isolated["nodes"]) == 1 and not isolated["edges"]
                for wrong_owner, wrong_company in [(str(uuid4()), "A"), (owner, "missing")]:
                    with pytest.raises(AppError) as error:
                        await service.get(wrong_owner, dataset, wrong_company, 1)
                    assert error.value.status == 404
                for i in range(25):
                    add("company", node=f"group-{i}")
                add(
                    "hyperedge",
                    members=[f"group-{i}" for i in range(25)] + ["A"],
                    data={"kind": "large"},
                )
                await session.commit()
                limited = await service.get(owner, dataset, "A", 1)
                assert limited["truncated"] and "member_limit" in limited["truncationReasons"]
                group = next(n for n in limited["nodes"] if n["label"] == "large")
                links = [e for e in limited["edges"] if e["source"] == group["id"]]
                assert len(links) == 12 and any(e["target"] == "node:A" for e in links)
                assert limited["omittedMembers"] == 14
                assert len(limited["nodes"]) <= limited["limits"]["nodes"]
                assert all(
                    e["source"] in {n["id"] for n in limited["nodes"]}
                    and e["target"] in {n["id"] for n in limited["nodes"]}
                    for e in limited["edges"]
                )
                for setting, maximum, reason in [
                    ("NODE_LIMIT", 3, "node_limit"),
                    ("EDGE_LIMIT", 2, "edge_limit"),
                    ("RECORD_LIMIT", 2, "record_limit"),
                ]:
                    with monkeypatch.context() as patch:
                        patch.setattr(dataset_service, setting, maximum)
                        bounded = await service.get(owner, dataset, "A", 3)
                        assert reason in bounded["truncationReasons"]
                        assert len(bounded["nodes"]) <= bounded["limits"]["nodes"]
                        assert len(bounded["edges"]) <= bounded["limits"]["edges"]
        finally:
            await engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(exercise())
