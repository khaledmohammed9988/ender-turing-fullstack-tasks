#!/bin/bash
set -Eeuo pipefail
cd /work/ender
set -a
source .env
set +a
suffix=$(date +%s)
for kind in migration regression; do
  runuser -u postgres -- createdb -O ender_review "ender_${kind}_${suffix}"
done
cd backend
MIGRATION_TEST_DATABASE_URL="postgresql+psycopg://ender_review:review-sandbox-only@127.0.0.1:5432/ender_migration_${suffix}" \
  ../.venv/bin/python ../scripts/check-migration.py | tee ../.evidence/migration-tests.txt
export DATABASE_URL="postgresql+psycopg://ender_review:review-sandbox-only@127.0.0.1:5432/ender_regression_${suffix}"
../.venv/bin/alembic upgrade head
../.venv/bin/python -m pytest tests -q --junitxml=../.evidence/regression-junit.xml | tee ../.evidence/regression-tests.txt
