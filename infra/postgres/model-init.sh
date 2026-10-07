#!/bin/sh
set -eu
export PGPASSWORD="$POSTGRES_PASSWORD"
psql -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 \
  -v model_password="$RISK_GNN_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE riskgnn LOGIN PASSWORD %L', :'model_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='riskgnn')\gexec
SELECT format('ALTER ROLE riskgnn PASSWORD %L', :'model_password')\gexec
SELECT 'CREATE DATABASE riskgnn OWNER riskgnn'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='riskgnn')\gexec
SQL
