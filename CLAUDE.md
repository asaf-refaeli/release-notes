# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

A small "Release Notes" service (API, minimal UI, Postgres) built for a DevOps home assignment. Most of the work is the infrastructure around it: a hardened image, a Helm chart, a CI/CD pipeline and a zero-downtime rollout. The backend lifecycle (DRAFT -> PUBLISHED -> ARCHIVED) and the audit trail follow the assignment spec exactly; keep everything else small.

The plan lives outside this repo in `../docs/project-plan.md`.

## Commands

- Install deps: `uv sync` (`uv.lock` is committed)
- Run: `uv run uvicorn app.main:app --reload` (needs `DATABASE_URL`)
- Tests: `uv run pytest` (needs Docker: testcontainers starts a real Postgres)
- Lint and format: `uv run ruff check . && uv run ruff format --check .`
- Migrations: `uv run alembic upgrade head` (needs `DATABASE_URL`)
- Runtime: Python 3.14, pinned in `.python-version`

Planned, not built yet (move each line up when its step lands):
- Build the image: `buildah bud -t release-notes:local .` (step 5). The container runs `uvicorn` directly (exec-form `CMD`, port `8080`), so it is PID 1 and receives SIGTERM for graceful shutdown.
- Container integration test: `scripts/integration-test.sh <image>` (step 5)
- Rollout check: `uv run scripts/rollout_check.py --url <base-url>` (step 9)

## Architecture

- `app/main.py`: assembles the app only: the `app` object, `lifespan` (creates the DB pool at startup, disposes it on shutdown), `/metrics`, `include_router`, one exception handler mapping each domain exception to an HTTP code via `STATUS_BY_ERROR`. Settings are validated at import, so bad config stops the process before it serves.
- `app/health.py`: router for `/healthz/live`, `/healthz/ready`, `/api/version`
- `app/config.py`: `Settings` from env vars only; `get_settings()` is not cached. Includes `DB_POOL_SIZE` (5) and `DB_MAX_OVERFLOW` (10).
- `app/log_config.py`: JSON logs to stdout; `/healthz/` access lines dropped
- `app/db.py`: `get_engine()` (one pool per process, sized from Settings, wires the pool gauges), SQL timing hooks on every engine, the `get_session` dependency, and the `EngineDep`/`SessionDep` aliases
- `app/metrics.py`: every app metric, defined once (`db_pool_checked_out`, `db_pool_max_connections`, `db_query_duration_seconds`, `release_lock_wait_seconds`); `http_requests_inprogress` comes from the instrumentator in `main.py`
- `app/models.py`: SQLAlchemy models `Release` and `ReleaseEvent` (the audit trail), plus the `ReleaseStatus` and `EventType` enums
- `app/schemas.py`: Pydantic request/response models; input models use `extra="forbid"`
- `app/service.py`: business rules and the `DomainError` exceptions; `_lock_release` (row lock) and `_record_event` are used by every lifecycle write; no HTTP code here
- `app/api.py`: `/api/releases` routes; thin, each calls one service function
- `migrations/`: Alembic; migrations must be expand-only so old pods keep working during a rollout. `env.py` reads `DATABASE_URL` via `get_settings()`; constraint names follow the naming convention on `Base`.
- `tests/conftest.py`: shared fixtures: one Postgres container and `alembic upgrade head` per run; `db_client` truncates all tables and points the app at the test DB for each test.

Rules:
- HTTP errors: `404` unknown release, `422` malformed body, `409` invalid transition or duplicate published version, `400` publish rule failed.
- Every lifecycle write is one transaction: `SELECT ... FOR UPDATE` on the release row, check the rule, update, insert the audit event, commit (ADR-0005).
- `/healthz/ready` checks the database; `/healthz/live` never does.

## Decisions
Decisions are documented as ADRs in `docs/adr/` using `docs/adr/0000-template.md` (`DECISIONS.md` index comes in step 0, before CI).
Their purpose is to explain why each choice was made.
- Use GitHub Flow as git workflow
- Use GitHub Actions for CI
- Separate GitOps repo (`gitops`); the Helm chart lives in this repo
- Sync routes with sync SQLAlchemy (ADR-0004)
- Concurrent writes: row lock plus a partial unique index (ADR-0005)
- Tests run against a real Postgres through testcontainers (ADR-0006)
<!-- Add each decision here once it's made. Until something is listed, ask before choosing. -->

## Conventions
- Commits: Conventional Commits (`feat:`, `fix:`, `test:`, `refactor:`, `ci:`, `chore:`, `docs:`)
- Every feature ships with its tests in the same commit: write the code, then the tests that cover it.
- Comments only where the reason isn't obvious. No emojis.
- Keep changes scoped to the task; propose new tools or dependencies before adding them.
- If code and docs disagree, fix the code or the doc in the same PR. Never document a bug.

## Security
- Do not run state-changing `kubectl`, `helm`, `kind` or `git push` commands unless asked. Read-only `kubectl` on the `kind-release-notes` context is fine.
- Do not read or write credentials, kubeconfigs, or `.env` files.
- Do not hardcode hostnames, tokens, or secrets.
