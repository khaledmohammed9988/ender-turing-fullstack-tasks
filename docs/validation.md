# Verification record — 10 November 2026

Validation ran in a private temporary Daytona sandbox using Python 3.14.10, PostgreSQL 15 and Bun 1.4.4. Cloud-only browser/dependency installation was used to avoid heavy workstation installs. The tested files were downloaded back into this local repository.

| Check | Result |
| --- | --- |
| Focused RBAC API tests, real PostgreSQL and JWT authentication | 14 passed |
| Adapted upstream backend regression suite | 58 passed |
| Infrastructure security/plan/lifecycle unit tests, mocked AWS | 15 passed |
| Browser tests for admin, manager and member | 3 passed |
| Total automated test cases | **90 passed; 0 failed** |
| Legacy schema backfill, downgrade, re-upgrade | Passed on a separate empty scratch database |
| Backend Ruff check | Passed after import/unused-import fixes |
| Vite build and TypeScript build check | Passed |
| Regenerated OpenAPI client and TanStack route tree | Included; metrics present, private helper absent |
| CloudFormation cfn-lint | Passed |
| Bootstrap shellcheck and rendered bash syntax | Passed |
| Official Docker Compose v2.39.4 checksum and Compose config parsing | Passed |
| Real AWS/Ghost/tunnel deployment | **Not performed** |
| Subsequent live Ghost/MySQL runtime on Daytona | **7 live checks passed; see runtime-validation.md** |
| Cloudflare Quick Tunnel attempt | **Failed: outbound connection resets; successful access used the Daytona preview proxy** |

The three browser cases use the built frontend and running backend. They verify member-hidden navigation, friendly denial for direct protected URLs, readable manager metrics/user list without admin controls, and admin controls. The admin case also creates a manager through the form, updates that account and deletes it. This is a focused RBAC browser suite, not certification of every inherited frontend test or upstream workflow.

During development, the first API run found an own-profile regression (3 failures); the condition was corrected and all 14 passed. The first frontend build caught route-generation order, error-prop typing and metrics-client typing errors. The broad backend suite initially found an SMTP fixture configuration issue; its transport was mocked and all 58 passed. The infrastructure check caught an optional `*` prefix in Docker's official checksum manifest; both bootstrap and validation now handle that format. No failure was hidden by reducing authorization requirements or skipping a failed case.

A final manual code review found that the create-user form sent its UI-only confirmation-password field to the newly strict API schema. The field is now removed before submission. The expanded browser workflow was rerun in a fresh temporary sandbox and passed all three cases, including real create/edit/delete requests. Backend focused tests and the frontend build also passed there. Transient Playwright download connection resets recovered through its official fallback mirrors.

The backend still emits an upstream Starlette/httpx deprecation warning. Some sandbox commands emitted Python environment-path normalization warnings; neither caused a test failure. No claim is made about CI execution, a one-hour timebox, production deployment, backups, external DNS reachability or Ghost ownership setup.

Local evidence (ignored by Git) is in `.evidence/`: JUnit XML, test logs, migration output, static-check logs, Compose validation output and three screenshots. `.review/validation.json` contains aggregate counts, verification boundaries and selected source hashes. Review these files before choosing any evidence to publish. AWS calls in unit tests use fake clients; they are not delivery receipts.

After the user requested an actual run and explicitly limited it to Daytona, an additional live container check was executed. Seven checks passed through the private Daytona preview. Details and boundaries are in `runtime-validation.md`; the original 90 automated test count is unchanged.
