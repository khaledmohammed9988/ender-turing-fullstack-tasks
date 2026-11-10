#!/bin/bash
set -Eeuo pipefail
cd /work/ender
mkdir -p .evidence
pg_version=$(pg_lsclusters --no-header | awk 'NR==1 {print $1}')
pg_ctlcluster "$pg_version" main start || pg_isready
runuser -u postgres -- psql -tc "SELECT 1 FROM pg_roles WHERE rolname='ender_review'" | grep -q 1 || \
  runuser -u postgres -- psql -c "CREATE ROLE ender_review LOGIN PASSWORD 'review-sandbox-only'" >/dev/null
runuser -u postgres -- psql -tc "SELECT 1 FROM pg_database WHERE datname='ender_review'" | grep -q 1 || \
  runuser -u postgres -- createdb -O ender_review ender_review
python - <<'PY'
import secrets, shlex
from pathlib import Path
if Path('.env').exists():
    raise SystemExit(0)
config={'DATABASE_URL':'postgresql+psycopg://ender_review:review-sandbox-only@127.0.0.1:5432/ender_review',
        'SECRET_KEY':secrets.token_urlsafe(40),'PROJECT_NAME':'Ender RBAC Review',
        'FIRST_SUPERUSER':'bootstrap@example.com','FIRST_SUPERUSER_PASSWORD':secrets.token_urlsafe(24),
        'FASTAPI_ENV':'development','RBAC_DEMO_PASSWORD':secrets.token_urlsafe(24)}
Path('.env').write_text(''.join(f'{k}={shlex.quote(v)}\n' for k,v in config.items()))
PY
set -a
source .env
set +a
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m pytest rbac_tests -q --junitxml=../.evidence/backend-junit.xml | tee ../.evidence/backend-tests.txt
../.venv/bin/python -m app.seed_rbac
../.venv/bin/python -c 'import json; from app.main import app; open("../frontend/openapi.json","w").write(json.dumps(app.openapi()))'
cd ../frontend
export PATH="$HOME/.bun/bin:$PATH"
bun install --frozen-lockfile
bun run generate-client
bun run build
cd ..
nohup .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 > .evidence/server.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" || true' EXIT
for attempt in $(seq 1 30); do
  curl --fail --silent http://127.0.0.1:8000/api/v1/utils/health-check/ >/dev/null && break
  sleep 1
done
cd frontend
bun x --bun playwright install --with-deps chromium
bun x --bun playwright test --config rbac.playwright.config.ts | tee ../.evidence/ui-tests.txt
