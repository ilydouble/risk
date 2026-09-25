#!/bin/sh
set -eu

attempt=0
until cypher-shell -a bolt://neo4j:7687 -u neo4j -p "$NEO4J_PASSWORD" 'RETURN 1' >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo 'Neo4j did not become ready' >&2
    exit 1
  fi
  sleep 2
done

cypher-shell -a bolt://neo4j:7687 -u neo4j -p "$NEO4J_PASSWORD" \
  'CREATE CONSTRAINT demo_node_identity IF NOT EXISTS FOR (n:DemoNode) REQUIRE (n.company_id, n.lang, n.id) IS UNIQUE'
