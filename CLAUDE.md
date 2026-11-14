# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

A small "Release Notes" service (API, minimal UI, Postgres) built for a DevOps home assignment. Most of the work is the infrastructure around it: a hardened image, a Helm chart, a CI/CD pipeline and a zero-downtime rollout. The backend lifecycle (DRAFT -> PUBLISHED -> ARCHIVED) and the audit trail follow the assignment spec exactly; keep everything else small.

The plan lives outside this repo in `../docs/project-plan.md`.

## Commands

<!-- Planned. Update each line once the step that adds it lands. -->
- Install deps: `uv sync` (`uv.lock` is committed)
- Run: `uv run uvicorn app.main:app --reload` (listens on `8080` in the container)
- Tests: `uv run pytest` (needs Docker: testcontainers starts a real Postgres)
- Lint and format: `uv run ruff check . && uv run ruff format --check .`
- Migrations: `uv run alembic upgrade head`
- Build the image: `buildah bud -t release-notes:local .`
- Container integration test: `scripts/integration-test.sh <image>`
- Rollout check: `uv run scripts/rollout_check.py --url <base-url>`
- Runtime: Python 3.13, pinned in `.python-version` and the `Dockerfile`

The container runs `uvicorn` directly (exec-form `CMD`), so it is PID 1 and receives SIGTERM for graceful shutdown.

## Architecture

<!-- Planned, update as code lands. -->
- `app/main.py`: `create_app()`, routers, exception handlers, `/healthz/live`, `/healthz/ready`, `/metrics`, `/api/version`
- `app/config.py`: `Settings` from env vars only
- `app/db.py`: engine and the `get_session` dependency
- `app/models.py`: SQLAlchemy models (`Release`, `ReleaseEvent`)
- `app/schemas.py`: Pydantic request/response models; input models use `extra="forbid"`
- `app/service.py`: business rules and domain exceptions; no HTTP code here
- `app/api.py`: `/api/releases` routes; maps exceptions to HTTP codes
- `migrations/`: Alembic; migrations must be expand-only so old pods keep working during a rollout

Rules:
- HTTP errors: `404` unknown release, `409` invalid transition or duplicate published version, `400` publish rule failed, `422` malformed body.
- Every lifecycle write is one transaction: `SELECT ... FOR UPDATE` on the release row, check the rule, update, insert the audit event, commit.
- `/healthz/ready` checks the database; `/healthz/live` never does.

## Decisions
Decisions are documented as ADRs in `docs/adr/` using `docs/adr/0000-template.md`, and indexed in `DECISIONS.md`.
Their purpose is to explain why each choice was made.
- Use GitHub Flow as git workflow
- Use GitHub Actions for CI
- Separate GitOps repo (`gitops`); the Helm chart lives in this repo
<!-- Add each decision here once it's made. Until something is listed, ask before choosing. -->

## Conventions
- Commits: Conventional Commits (`feat:`, `fix:`, `test:`, `refactor:`, `ci:`, `chore:`, `docs:`)
- Tests first: write the failing test, then the code.
- Comments only where the reason isn't obvious. No emojis.
- Keep changes scoped to the task; propose new tools or dependencies before adding them.
- If code and docs disagree, fix the code or the doc in the same PR. Never document a bug.

## Security
- Do not run state-changing `kubectl`, `helm`, `kind` or `git push` commands unless asked. Read-only `kubectl` on the `kind-release-notes` context is fine.
- Do not read or write credentials, kubeconfigs, or `.env` files.
- Do not hardcode hostnames, tokens, or secrets.
