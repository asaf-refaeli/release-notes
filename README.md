# release-notes

A small internal service for recording what shipped in each release: a FastAPI API on Postgres, with a draft → published → archived lifecycle and an audit trail of every change.

> **Status:** home assignment, in progress. Built: the service with health checks, structured logs, metrics, the release lifecycle, the audit trail, a UI for all of it, and a hardened container image. Next: a Helm chart, CI/CD and a zero-downtime rollout.

## Quickstart

Needs Python 3.14, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync
docker run -d --name rn-db -p 5432:5432 \
  -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=release_notes postgres:18
export DATABASE_URL=postgresql+psycopg://app:app@127.0.0.1:5432/release_notes
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/ for the UI (create, edit, publish and archive releases, and see each release's history), http://127.0.0.1:8000/docs for the API, or:

```bash
curl -X POST localhost:8000/api/releases -H 'Content-Type: application/json' \
  -d '{"version": "1.0.0", "description": "First release"}'
curl -X POST localhost:8000/api/releases/1/publish
curl localhost:8000/api/releases/1/events
```

## API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/api/releases` | Create a release (always starts as `DRAFT`) |
| `GET` | `/api/releases` | List releases, newest first (`limit`, `offset`) |
| `GET` | `/api/releases/{id}` | Get one release |
| `PATCH` | `/api/releases/{id}` | Edit `version` or `description` (drafts only) |
| `POST` | `/api/releases/{id}/publish` | Publish a draft; the server sets `published_at` |
| `POST` | `/api/releases/{id}/archive` | Archive a published release |
| `GET` | `/api/releases/{id}/events` | Audit history: `CREATED`, `UPDATED`, `PUBLISHED`, `ARCHIVED` |
| `GET` | `/healthz/live`, `/healthz/ready` | Liveness (no I/O) and readiness (checks the database) |
| `GET` | `/api/version` | Running app version |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/` | The UI (static files from `app/static/`) |

**Lifecycle rules:** only drafts can be edited or published; only published releases can be archived; an archived release is final. Publishing needs a non-blank description and a version no other published or archived release uses.

**Errors:** `404` unknown release, `409` invalid transition or duplicate version, `400` blank description on publish, `422` malformed request.

## How consistency is kept

- Each change and its audit event are saved in **one transaction**: both or neither.
- Concurrent writes to the same release are serialized by a **row lock** (`SELECT ... FOR UPDATE`); duplicate published versions are blocked by a **partial unique index**. See [ADR-0005](docs/adr/0005-concurrent-writes.md).
- Tests prove it with real parallel requests: removing the lock makes them fail.

## Configuration

Environment variables only:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | required | Postgres URL (`postgresql+psycopg://...`); the app does not start without it |
| `APP_VERSION` | `dev` | Shown by `/api/version` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`; logs are JSON on stdout |
| `DB_POOL_SIZE` | `5` | DB connections kept open per process |
| `DB_MAX_OVERFLOW` | `10` | Extra connections allowed under load |

## Observability

Besides the standard HTTP metrics (request count, latency, status), `/metrics` exposes:

| Metric | Answers |
|---|---|
| `db_pool_checked_out` / `db_pool_max_connections` | How full is the DB connection pool? |
| `db_query_duration_seconds` | Is Postgres slow? |
| `release_lock_wait_seconds` | Do writes wait for each other's row lock? |
| `http_requests_inprogress` | Are requests queuing for worker threads? |

## Tests

```bash
uv run pytest                                          # needs Docker: starts a real Postgres 18
uv run ruff check . && uv run ruff format --check .    # lint and format
```

Tests run against a real Postgres (testcontainers), including the migrations, concurrent publishes, and an audit-trail rollback check.

## Container image

Needs [Buildah](https://buildah.io/) and [Podman](https://podman.io/) (both rootless, no Docker daemon), plus `curl` and `jq` for the smoke test.

```bash
buildah build --layers -t release-notes:local .
scripts/smoke-test.sh localhost/release-notes:local
```

- Two stages on `python:3.14.10-slim-trixie` (pinned by digest): only the locked runtime packages and the app ship; no build tools, no pip.
- Runs as UID 10001 on a read-only filesystem with no capabilities; Uvicorn is PID 1 on port `8080` and finishes in-flight requests for up to 20 s on SIGTERM.
- The same image runs the migrations: `alembic upgrade head` instead of the default command.
- The smoke test starts Postgres, the migrations and the app in one Podman pod with those restrictions, then checks readiness, a create and read back, the UI, and a clean exit on SIGTERM. pytest covers the logic; this covers the image.

See [ADR-0008](docs/adr/0008-container-image.md) and [ADR-0009](docs/adr/0009-one-image.md).

## Repository layout

```
app/          FastAPI app: routes (api.py, health.py), rules (service.py), models, settings, metrics
app/static/   The UI: index.html, app.js, app.css (no build step; security headers in app/ui.py)
migrations/   Alembic migrations (expand-only, safe during a rolling update)
tests/        pytest suite
docs/adr/     Architecture decision records
scripts/      smoke-test.sh: container smoke test
Dockerfile    The container image
```

## Decisions

| ADR | Decision |
|---|---|
| [0001](docs/adr/0001-git-workflow.md) | GitHub Flow with squash merges |
| [0002](docs/adr/0002-ci-platform.md) | GitHub Actions for CI |
| [0003](docs/adr/0003-helm-chart-location.md) | Helm chart in this repo; deployment state in a separate GitOps repo |
| [0004](docs/adr/0004-request-handling-sync.md) | Sync routes with sync SQLAlchemy |
| [0005](docs/adr/0005-concurrent-writes.md) | Row lock plus a partial unique index for concurrent writes |
| [0006](docs/adr/0006-tests-on-real-postgres.md) | Tests run against a real Postgres through testcontainers |
| [0007](docs/adr/0007-ui-vanilla-js.md) | UI: static files and plain JavaScript on the JSON API, strict CSP |
| [0008](docs/adr/0008-container-image.md) | Container image: Python slim, two stages, non-root, read-only |
| [0009](docs/adr/0009-one-image.md) | One image for the app, the migration Job and the UI |
