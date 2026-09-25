"""Idempotent demo fixture provisioning. Existing rows and graph facts are never overwritten."""

import asyncio
import json
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from neo4j import AsyncGraphDatabase
from sqlalchemy.dialects.postgresql import insert

from risk_api.models import Company, User
from risk_api.shared.config import settings
from risk_api.shared.db import session_factory


async def seed_company_rows(records: list[dict[str, Any]]) -> None:
    hasher = PasswordHasher()
    async with session_factory() as session:
        await session.execute(
            insert(User)
            .values(
                id="demo-user",
                username=settings.demo_user,
                password_hash=hasher.hash(settings.demo_password),
                display_name="演示用户",
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        for record in records:
            company = record["company"]
            await session.execute(
                insert(Company)
                .values(
                    id=company["id"],
                    name_cn=company["nameCn"],
                    name_en=company["nameEn"],
                    reg_no=company["regNo"],
                    region=company["region"],
                    sector=company["sector"],
                    risk_level=company["riskLevel"],
                    credit_score=company["creditScore"],
                    summary=company,
                    profile=record["profile"],
                    scores=record["scores"],
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
        await session.commit()


async def seed_graph_rows(records: list[dict[str, Any]]) -> None:
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    try:
        async with driver.session() as session:
            for record in records:
                company_id = record["company"]["id"]
                for lang, graph in record["graphs"].items():
                    nodes = [
                        {"id": node["id"], "hop": node["hop"], "payload": json.dumps(node)}
                        for node in graph["nodes"]
                    ]
                    edges = [
                        {
                            "id": edge["id"],
                            "source": edge["source"],
                            "target": edge["target"],
                            "payload": json.dumps(edge),
                        }
                        for edge in graph["edges"]
                    ]
                    await session.run(
                        "UNWIND $nodes AS item "
                        "MERGE (n:DemoNode {company_id: $company_id, lang: $lang, id: item.id}) "
                        "ON CREATE SET n.hop = item.hop, n.payload = item.payload",
                        company_id=company_id,
                        lang=lang,
                        nodes=nodes,
                    )
                    await session.run(
                        "UNWIND $edges AS item "
                        "MATCH (a:DemoNode {company_id: $company_id, lang: $lang, "
                        "id: item.source}) "
                        "MATCH (b:DemoNode {company_id: $company_id, lang: $lang, "
                        "id: item.target}) "
                        "MERGE (a)-[r:RELATED {company_id: $company_id, "
                        "lang: $lang, id: item.id}]->(b) "
                        "ON CREATE SET r.payload = item.payload",
                        company_id=company_id,
                        lang=lang,
                        edges=edges,
                    )
    finally:
        await driver.close()


async def main() -> None:
    records: list[dict[str, Any]] = json.loads(
        (Path(__file__).resolve().parents[2] / "seed" / "demo.json").read_text()
    )
    await seed_company_rows(records)
    await seed_graph_rows(records)


if __name__ == "__main__":
    asyncio.run(main())
