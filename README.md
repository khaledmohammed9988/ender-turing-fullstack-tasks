# Ender Turing Full-Stack preparation

Two application exercises in one repository: FastAPI/React RBAC and plan-first Ghost provisioning. AI assistance and copied task-conversation excerpts are disclosed in `ai-conversations/`. No AWS resources were created during verification.

- Task brief: https://github.com/evios/Fullstack-Dev-Test-Task
- Careers: https://enderturing.com/careers
- Actual base template: https://github.com/fastapi/full-stack-fastapi-template
- Base commit: `aabb90126964a164e02aff39e7c385bb0598236d`
- Original template documentation: `UPSTREAM_README.md`; original MIT license retained.

## Task 1: role-based access control

| Capability | Admin | Manager | Member |
| --- | --- | --- | --- |
| Read/update own profile and password | Yes | Yes | Yes |
| Basic app and own items | Yes | Yes | Yes |
| Read users/list users | Yes | Yes | Own profile only |
| Read metrics | Yes | Yes | No |
| Create, update, delete other users; assign roles | Yes | No | No |
| Read/update/delete another user's items | Yes | No | No |

Administrators cannot delete, demote or deactivate themselves through the management endpoints. A member's self-service account deletion remains available, as in the template. Managers can delete their own accounts too; they cannot manage other accounts.

### Design

The database `role` is the canonical authority. Three fixed roles map to explicit permissions in `backend/app/authorization.py`. FastAPI dependencies enforce those permissions on user administration and metrics; the existing item ownership rules are retained with an administrator override. Every authenticated request reloads the database user, so a role change takes effect with an already issued JWT. No role claim in a JWT grants access. The old `is_superuser` column is a compatibility mirror, maintained by CRUD and computed from the role in public responses.

Public signup and own-profile updates have narrow schemas that forbid extra fields, including `role` and `is_superuser`. Admin-only creation/update can assign a validated role. A migration backfills legacy administrators and adds a database role constraint; new users default to member. The unauthenticated development user-creation router is not registered. Denials log only user ID and required permission. Missing/invalid authentication returns 401; authenticated permission denial returns 403.

The React frontend reads server-provided capabilities. Managers see the Users table and Metrics but no user-management controls; members see neither navigation entry. Route guards fetch the current user before opening either protected route and render a friendly Access denied view for direct URLs. A 403 preserves the login session. Role dropdowns replace the old superuser checkbox, and the OpenAPI client is regenerated from the modified backend rather than hand-edited.

### Setup and run

Use Python **3.14**, uv, Bun (verified with **1.4.4**) and PostgreSQL (verified with **15**). Heavy installation/builds were performed in a private temporary Daytona sandbox, not on the local workstation.

1. Copy `.env.example` to `.env`. Set a dedicated PostgreSQL `DATABASE_URL`, a strong `SECRET_KEY`, `FIRST_SUPERUSER`, a strong `FIRST_SUPERUSER_PASSWORD`, `PROJECT_NAME`, and `FASTAPI_ENV=development`. The example values are placeholders. Do not commit the operator's `.env`.
2. Install the locked backend dependencies from the repository root:

```sh
uv sync --frozen --package app --group dev
cd backend
uv run alembic upgrade head
# Choose a temporary demo password of at least 12 characters in your shell:
export RBAC_DEMO_PASSWORD='<operator-selected-demo-password>'
uv run python -m app.seed_rbac
cd ../frontend
bun install --frozen-lockfile
# From backend/, generate the schema after loading the settings above:
# uv run python -c 'import json; from app.main import app; open("../frontend/openapi.json","w").write(json.dumps(app.openapi()))'
bun run generate-client
bun run build
cd ../backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The development seed creates `admin@example.com`, `manager@example.com` and `member@example.com` with the supplied demo password. It does not reset existing accounts. Never seed these predictable accounts into a public deployment. For frontend hot reload, run `bun run dev` separately and follow the template's API/CORS configuration.

`bun run build` runs Vite first to regenerate the TanStack route tree, then TypeScript checking. The built app is served by FastAPI. `frontend/openapi.json`, generated client files and the generated route tree are included for review; compiled bundles are not.

### Verification

Use a disposable database. The upstream regression suite deletes its test data; never point it at a real application database.

```sh
cd backend
uv run pytest rbac_tests -q
uv run pytest tests -q
# With the built app running and the demo password exported:
cd ../frontend
bun x --bun playwright install chromium
bun x --bun playwright test --config rbac.playwright.config.ts
```

The focused tests cover the role matrix, protected mutations, safe response fields, signup/profile injection, database role changes with existing tokens, authentication failures and self-lockout prevention. Browser tests exercise navigation and direct URLs for all three roles. `scripts/check-migration.py` separately tests old-schema backfill, downgrade and re-upgrade against an explicitly supplied empty scratch database.

Cloud validation scripts in `scripts/` are intended for an isolated root Linux sandbox. They install test dependencies and create disposable PostgreSQL databases; they are not workstation setup scripts. See `docs/validation.md` for the executed results and limits.

## Task 2: one-command Ghost provisioning

See `infrastructure/README.md`. A Python command generates an AWS CloudFormation plan; adding `--execute` provisions a fresh VM with Ghost, MySQL and outbound Cloudflare Tunnel. There are zero inbound security-group rules, no SSH key, and no published container ports. Images use immutable digests; the tunnel token comes from one pre-existing SSM SecureString parameter.

The pinned Ghost/MySQL containers were run successfully in a temporary Daytona Docker sandbox. Seven live checks passed, including independent authenticated HTTPS access, blocked admin/writes, and content/database marker persistence after restart. Cloudflare Quick Tunnel registration failed with outbound connection resets; the successful external check used Daytona's private preview proxy and a loopback-only read-only gateway. AWS provisioning, IAM/SSM and the named Cloudflare connector remain untested. See `docs/runtime-validation.md` and `infrastructure/smoke/README.md` for the exact scope.

## Review material

Read `NOTES.md`, `docs/validation.md`, `docs/runtime-validation.md`, and `ai-conversations/copied-visible-task-exchange.md`. Sanitized test output and demo screenshots are in `docs/verification/`. Operator environment files and local tools/evidence remain ignored. Upstream release, issue-management and deployment automations were removed from this assessment snapshot; the only included workflow runs tests and static checks. It creates no cloud infrastructure and needs no cloud credentials.
