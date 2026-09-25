import json
from typing import Any

from neo4j import AsyncDriver


class GraphRepository:
    def __init__(self, driver: AsyncDriver):
        self.driver = driver

    async def get(self, company_id: str, lang: str, depth: int) -> dict[str, Any] | None:
        # Seeded hop is the shortest distance from the root; read both facts from Neo4j.
        async with self.driver.session() as session:
            nodes_result = await session.run(
                "MATCH (n:DemoNode {company_id: $company_id, lang: $lang}) "
                "WHERE n.hop <= $depth RETURN n.payload AS payload ORDER BY n.hop, n.id",
                company_id=company_id,
                lang=lang,
                depth=depth,
            )
            nodes = [json.loads(record["payload"]) async for record in nodes_result]
            if not nodes:
                return None
            ids = [node["id"] for node in nodes]
            edges_result = await session.run(
                "MATCH (a:DemoNode {company_id: $company_id, lang: $lang})"
                "-[r:RELATED {company_id: $company_id, lang: $lang}]->"
                "(b:DemoNode {company_id: $company_id, lang: $lang}) "
                "WHERE a.id IN $ids AND b.id IN $ids RETURN r.payload AS payload ORDER BY r.id",
                company_id=company_id,
                lang=lang,
                ids=ids,
            )
            edges = [json.loads(record["payload"]) async for record in edges_result]
            root = next((node["id"] for node in nodes if node["hop"] == 0), company_id)
            return {"rootId": root, "nodes": nodes, "edges": edges}
