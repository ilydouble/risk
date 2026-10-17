"""Bounded source-data graphs. Dataset IDs, not model IDs, scope all queries."""

import asyncio
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from risk_api.errors import AppError
from risk_api.modules.graph.dataset_repository import DatasetGraphRepository
from risk_api.modules.modeling.repository import ModelingRepository
from risk_api.modules.modeling.workbench_model import EnterpriseImport, EnterpriseRecord

DEMO_DATASET_ID = "demo-companies"
NODE_LIMIT = 100
EDGE_LIMIT = 240
RECORD_LIMIT = 100
MEMBER_LIMIT = 12


class DatasetGraphService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = DatasetGraphRepository(session)

    async def get(self, owner: str, dataset_id: str, company_id: str, depth: int) -> dict:
        try:
            identity = str(UUID(dataset_id))
        except ValueError as exc:
            raise AppError(
                422, "GRAPH_INPUT_INVALID", "dataset_id must be a dataset UUID", field="datasetId"
            ) from exc
        try:
            async with asyncio.timeout(6):
                # Transaction-local: the request/tool session is closed after this operation.
                await self.session.execute(text("SET LOCAL statement_timeout = '2000ms'"))
                return await self._query(owner, identity, company_id, depth)
        except TimeoutError as exc:
            raise AppError(
                503, "GRAPH_QUERY_TIMEOUT", "Graph query timed out; reduce depth"
            ) from exc
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) == "57014":
                raise AppError(503, "GRAPH_QUERY_TIMEOUT", "Graph query timed out") from exc
            raise

    async def _query(self, owner: str, identity: str, company_id: str, depth: int) -> dict:
        dataset = await ModelingRepository(self.session).dataset(owner, identity)
        if await self.session.get(EnterpriseImport, identity) is None:
            raise AppError(409, "GRAPH_DATA_UNAVAILABLE", "Dataset enterprise data is not imported")
        record = EnterpriseRecord
        center = await self.session.scalar(
            select(record).where(
                record.dataset_id == identity,
                record.kind == "company",
                record.node_id == company_id,
            )
        )
        if center is None:
            raise AppError(404, "GRAPH_COMPANY_NOT_FOUND", "Company not found in this dataset")
        snapshot = center.snapshot
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        reasons: set[str] = set()
        seen: set[int] = set()
        visited: set[str] = set()
        frontier = {company_id}
        omitted_members = 0

        def entity(row: dict) -> dict:
            return {
                "id": "node:" + row["node_id"],
                "entityId": row["node_id"],
                "kind": row["kind"],
                "label": (row["name"] or row["node_id"])[:256],
                "recordSequence": row["sequence"],
                "data": {},
            }

        nodes["node:" + company_id] = entity(
            {
                "node_id": company_id,
                "kind": "company",
                "name": str(center.data.get("name") or company_id)[:256],
                "sequence": center.sequence,
            }
        )
        for _ in range(depth):
            if not frontier:
                break
            rows = await self.repository.neighbors(
                identity, snapshot, frontier, seen, RECORD_LIMIT - len(seen) + 1, MEMBER_LIMIT
            )
            remaining = RECORD_LIMIT - len(seen)
            if len(rows) > remaining:
                reasons.add("record_limit")
            rows = rows[:remaining]
            next_frontier: set[str] = set()
            for row in rows:
                seen.add(row["sequence"])
                kind = row["kind"]
                if kind == "hyperedge":
                    # Keep queried members even if they are late in the original large group.
                    refs = list(dict.fromkeys(sorted(row["anchors"]) + row["members"]))[
                        :MEMBER_LIMIT
                    ]
                    omitted_members += row["member_count"] - len(refs)
                    if row["member_count"] > len(refs):
                        reasons.add("member_limit")
                else:
                    refs = list(dict.fromkeys(v for v in (row["source"], row["target"]) if v))
                missing = [ref for ref in refs if "node:" + ref not in nodes]
                extra = int(kind != "edge")
                added_edges = len(refs) if kind == "hyperedge" else 1
                if len(nodes) + len(missing) + extra > NODE_LIMIT:
                    reasons.add("node_limit")
                    continue
                if len(edges) + added_edges > EDGE_LIMIT:
                    reasons.add("edge_limit")
                    continue
                resolved = await self.session.execute(
                    select(
                        record.node_id,
                        record.kind,
                        record.sequence,
                        record.data["name"].astext.label("name"),
                    )
                    .where(
                        record.dataset_id == identity,
                        record.snapshot == snapshot,
                        record.node_id.in_(missing),
                        record.kind.in_(("company", "person")),
                    )
                    .order_by(record.sequence)
                )
                found = list(resolved.mappings())
                if len(found) != len(missing):
                    raise AppError(
                        409, "GRAPH_DATA_INVALID", "Graph contains unresolved references"
                    )
                for node in found:
                    nodes["node:" + node["node_id"]] = entity(dict(node))
                key = f"{kind}:{row['sequence']}"
                label = str(
                    row["data"].get("relation")
                    or row["data"].get("kind")
                    or row["data"].get("type")
                    or kind
                )
                info = {**row["data"], "snapshot": snapshot}
                if kind != "edge":
                    nodes[key] = {
                        "id": key,
                        "entityId": None,
                        "kind": kind,
                        "label": label,
                        "recordSequence": row["sequence"],
                        "data": {**info, "memberCount": row["member_count"]},
                    }
                pairs = (
                    [("node:" + row["source"], "node:" + row["target"])]
                    if kind == "edge"
                    else [(key, "node:" + ref) for ref in refs]
                )
                for index, (source, target) in enumerate(pairs):
                    edges.append(
                        {
                            "id": f"{key}:{index}",
                            "source": source,
                            "target": target,
                            "kind": kind,
                            "label": label,
                            "directed": kind == "edge",
                            "recordSequence": row["sequence"],
                            "data": info,
                        }
                    )
                if kind != "event":
                    next_frontier.update(refs)
            visited.update(frontier)
            frontier = next_frontier - visited
            if len(seen) >= RECORD_LIMIT:
                if frontier:
                    reasons.add("record_limit")
                break
        return {
            "datasetId": identity,
            "datasetName": dataset.name,
            "snapshot": snapshot,
            "companyId": company_id,
            "depth": depth,
            "demo": False,
            "rootId": "node:" + company_id,
            "nodes": list(nodes.values()),
            "edges": edges,
            "truncated": bool(reasons),
            "truncationReasons": sorted(reasons),
            "omittedMembers": omitted_members,
            "limits": {
                "nodes": NODE_LIMIT,
                "edges": EDGE_LIMIT,
                "records": RECORD_LIMIT,
                "membersPerGroup": MEMBER_LIMIT,
            },
        }


def demo_graph(graph: dict, company_id: str, depth: int) -> dict:
    """Adapt the existing seeded graph without changing its historical page contract."""
    kept_nodes = graph["nodes"][:NODE_LIMIT]
    ids = {node["id"] for node in kept_nodes}
    kept_edges = [
        edge for edge in graph["edges"] if edge["source"] in ids and edge["target"] in ids
    ]
    reasons = []
    if len(graph["nodes"]) > NODE_LIMIT:
        reasons.append("node_limit")
    if len(kept_edges) > min(EDGE_LIMIT, RECORD_LIMIT):
        reasons.append("record_limit")
    kept_edges = kept_edges[: min(EDGE_LIMIT, RECORD_LIMIT)]
    return {
        "datasetId": DEMO_DATASET_ID,
        "datasetName": "Shared demo companies",
        "snapshot": "seed",
        "companyId": company_id,
        "depth": depth,
        "demo": True,
        "rootId": graph["rootId"],
        "nodes": [
            {
                "id": n["id"],
                "label": n["label"],
                "kind": "person" if n["type"] in {"person", "owner"} else "company",
                "entityId": n.get("companyId"),
                "recordSequence": None,
                "data": {"relation": n.get("relation"), "note": n.get("note")},
            }
            for n in kept_nodes
        ],
        "edges": [
            {
                "id": e["id"],
                "source": e["source"],
                "target": e["target"],
                "kind": "edge",
                "label": e["label"],
                "directed": True,
                "recordSequence": None,
                "data": {"relation": e["type"]},
            }
            for e in kept_edges
        ],
        "truncated": bool(reasons),
        "truncationReasons": reasons,
        "omittedMembers": 0,
        "limits": {
            "nodes": NODE_LIMIT,
            "edges": EDGE_LIMIT,
            "records": RECORD_LIMIT,
            "membersPerGroup": MEMBER_LIMIT,
        },
    }
