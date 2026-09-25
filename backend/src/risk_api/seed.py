"""Idempotent demo fixture provisioning. Existing rows and graph facts are never overwritten."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from neo4j import AsyncGraphDatabase
from sqlalchemy.dialects.postgresql import insert

from risk_api.modules.company.model import Company
from risk_api.shared.config import settings
from risk_api.shared.db import session_factory
from risk_api.shared.logging import configure_logging

# `python -m risk_api.seed` executes this file as __main__; keep its logger in the app namespace.
logger = logging.getLogger("risk_api.seed")


async def seed_company_rows(records: list[dict[str, Any]]) -> None:
    async with session_factory() as session:
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


def load_demo_records() -> list[dict[str, Any]]:
    seed_dir = Path(__file__).resolve().parents[2] / "seed" / "demo"
    paths = sorted(seed_dir.glob("C-*.json"))
    if not paths:
        raise RuntimeError(f"No demo fixtures found in {seed_dir}")
    records: list[dict[str, Any]] = []
    for path in paths:
        record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if record["company"]["id"] != path.stem:
            raise ValueError(f"Demo fixture ID does not match filename: {path}")
        records.append(record)
    return records


async def main() -> None:
    records = load_demo_records()
    logger.info("demo_seed.started", extra={"fixture_count": len(records)})
    await seed_company_rows(records)
    await seed_graph_rows(records)
    logger.info("demo_seed.completed", extra={"fixture_count": len(records)})


if __name__ == "__main__":
    configure_logging(settings.log_level, output_format=settings.log_format)
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("demo_seed.failed")
        raise SystemExit(1) from None
