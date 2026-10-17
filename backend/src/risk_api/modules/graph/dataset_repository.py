"""Snapshot-scoped reads for the normalized enterprise graph."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

NEIGHBORS = text("""
                SELECT sequence,kind,source,target,
                  jsonb_path_query_array(members, CAST(:member_path AS jsonpath)) AS members,
                  (SELECT coalesce(jsonb_agg(value), '[]'::jsonb)
                   FROM jsonb_array_elements_text(members) m(value)
                   WHERE value = ANY(CAST(:frontier AS text[]))) AS anchors,
                  jsonb_array_length(members) AS member_count,
                  jsonb_build_object(
                    'relation',left(data->>'relation',128), 'kind',left(data->>'kind',128),
                    'type',left(data->>'type',128),
                    'time',left(coalesce(data->>'time',data->>'date'),128),
                    'properties',(SELECT jsonb_object_agg(key,left(value::text,256)) FROM
                      (SELECT key,value FROM jsonb_each(data) WHERE key!='sourceRecord'
                       ORDER BY key LIMIT 20) props),
                    'weight',data->'weight',
                    'sourceRecord',jsonb_build_object(
                      'filename',left(data->'sourceRecord'->>'filename',255),
                      'path',left(data->'sourceRecord'->>'path',512),
                      'sha256',left(data->'sourceRecord'->>'sha256',64))) AS data
                FROM workbench_enterprise_records
                WHERE dataset_id=:dataset AND snapshot=:snapshot
                  AND kind IN ('edge','hyperedge','event')
                  AND sequence <> ALL(CAST(:seen AS integer[]))
                  AND (source=ANY(CAST(:frontier AS text[]))
                    OR target=ANY(CAST(:frontier AS text[]))
                    OR members ?| CAST(:frontier AS text[]))
                ORDER BY sequence LIMIT :limit
            """)


class DatasetGraphRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def neighbors(
        self,
        dataset: str,
        snapshot: str,
        frontier: set[str],
        seen: set[int],
        limit: int,
        member_limit: int,
    ) -> list[dict]:
        result = await self.session.execute(
            NEIGHBORS,
            {
                "dataset": dataset,
                "snapshot": snapshot,
                "frontier": sorted(frontier),
                "seen": sorted(seen),
                "limit": limit,
                "member_path": f"$[0 to {member_limit - 1}]",
            },
        )
        return [dict(row) for row in result.mappings()]
