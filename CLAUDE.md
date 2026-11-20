# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

A small "Release Notes" service (API, minimal UI, Postgres) built for a DevOps home assignment. Most of the work is the infrastructure around it: a hardened image, a Helm chart, a CI/CD pipeline and a zero-downtime rollout. The backend lifecycle (DRAFT -> PUBLISHED -> ARCHIVED) and the audit trail follow the assignment spec exactly; keep everything else small.

The plan lives outside this repo in `../docs/project-plan.md`.

## Commands

- Install deps: `uv sync` (`uv.lock` is committed)
- Run: `uv run uvicorn app.main:app --reload` (needs `DATABASE_URL`); the UI is at `http://127.0.0.1:8000/`
- Tests: `uv run pytest` (needs Docker: testcontainers starts a real Postgres)
- Lint and format: `uv run ruff check . && uv run ruff format --check .`
- Migrations: `uv run alembic upgrade head` (needs `DATABASE_URL`)
- Runtime: Python 3.14, pinned in `.python-version`
- Build the image: `buildah build --layers -t release-notes:local .` (rootless Buildah; Docker cannot see the result, Podman can). The container runs `uvicorn` directly (exec-form `CMD`, port `8080`), so it is PID 1 and receives SIGTERM for graceful shutdown.
- Container smoke test: `scripts/smoke-test.sh localhost/release-notes:local` (needs Podman, curl, jq)

Planned, not built yet (move each line up when it lands):
- Rollout check: `uv run scripts/rollout_check.py --url <base-url>`

## Architecture

- `app/main.py`: assembles the app only: the `app` object, `lifespan` (creates the DB pool at startup, disposes it on shutdown), `/metrics`, `include_router`, the `security_headers` middleware, `app.frontend("/", ...)` after the routers (routes match first, then files), one exception handler mapping each domain exception to an HTTP code via `STATUS_BY_ERROR`. Settings are validated at import, so bad config stops the process before it serves.
- `app/ui.py`: `STATIC_DIR` (built from `__file__`, so any working directory works), `CONTENT_SECURITY_POLICY`, and the `security_headers` middleware (CSP on everything except `/docs` and `/redoc`, plus `nosniff` and `no-cache`)
- `app/static/`: the UI (ADR-0007): `index.html`, `app.js` (an ES module calling the JSON API), `app.css`, `favicon.svg`. Served with `fallback=None`, so unknown URLs are 404.
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
- `Dockerfile`: two stages on `python:3.14.10-slim-trixie` (tag + digest). The builder copies `pyproject.toml` + `uv.lock` and runs `uv sync --locked --no-dev`; the runtime copies the venv, `alembic.ini`, `migrations/` and `app/`, removes pip, runs as `USER 10001` with root-owned files (ADR-0008). The same image runs the migration Job (`alembic upgrade head`) (ADR-0009). Keep `pyproject.toml` and `uv.lock` as a `COPY`, not a bind mount: Buildah's layer cache ignores bind-mounted file contents.
- `.dockerignore`: `.git`, `.venv`, `__pycache__`, `.env*`; the `COPY` lines name every path the image needs, never `COPY . .`.
- `scripts/smoke-test.sh`: container smoke test (bash). Runs Postgres, the migrations and the app in one Podman pod with the Kubernetes restrictions (read-only with no `/tmp`, no capabilities, no `--user` so the image's own user is checked), then checks readiness, create + read back, the UI, and exit code 0 on SIGTERM.
- `tests/conftest.py`: shared fixtures: one Postgres container and `alembic upgrade head` per run; `db_client` truncates all tables and points the app at the test DB for each test.

Rules:
- HTTP errors: `404` unknown release, `422` malformed body, `409` invalid transition or duplicate published version, `400` publish rule failed.
- Every lifecycle write is one transaction: `SELECT ... FOR UPDATE` on the release row, check the rule, update, insert the audit event, commit (ADR-0005).
- `/healthz/ready` checks the database; `/healthz/live` never does.
- API error messages are shown to people as they are: name the version, not the id, and say what to do.
- UI: user data reaches the page only through `textContent` (never `innerHTML` and similar); no inline `<script>`, `style=` or `on*=` (the CSP blocks them); API URLs in JS are relative; no CDN, no build step. Element ids are the contract between `index.html` and `app.js` (a test checks them).

## Decisions
Decisions are documented as ADRs in `docs/adr/` using `docs/adr/0000-template.md` (a `DECISIONS.md` index comes before CI).
Their purpose is to explain why each choice was made.
- Use GitHub Flow as git workflow
- Use GitHub Actions for CI
- Separate GitOps repo (`gitops`); the Helm chart lives in this repo
- Sync routes with sync SQLAlchemy (ADR-0004)
- Concurrent writes: row lock plus a partial unique index (ADR-0005)
- Tests run against a real Postgres through testcontainers (ADR-0006)
- UI: static files and plain JavaScript on the JSON API, strict CSP (ADR-0007)
- Container image: Python slim, two stages, non-root, read-only (ADR-0008)
- One image for the app, the migration Job and the UI (ADR-0009)
- Migration ordering: Argo CD Sync hook and sync waves, DB -1, Job 0, app 1 (ADR-0010)
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
