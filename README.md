# release-notes

A small internal service for recording what shipped in each release: a FastAPI API on Postgres, with a draft → published → archived lifecycle and an audit trail of every change.

> **Status:** home assignment, in progress. Built: the service with health checks, structured logs, metrics, the release lifecycle, the audit trail, a UI for all of it, a hardened container image, and a Helm chart for the app, its Postgres and the migrations. Next: the GitOps deployment, CI/CD and a zero-downtime rollout.

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

## Helm chart

`chart/` deploys the app, its Postgres and the schema migration. Argo CD installs it from the [gitops](https://github.com/asaf-refaeli/gitops) repo, which holds the per-environment values.

| Resources | What they do |
|---|---|
| Deployment, Service, ServiceAccount | The app on container port `8080` (named `http`); the Service listens on `80`. The pods get no Kubernetes API token. |
| HorizontalPodAutoscaler | On CPU, off by default (`autoscaling.enabled`, needs metrics-server). When on, it owns the replica count. |
| PodDisruptionBudget | On by default, `maxUnavailable: 1`: a node drain evicts one app pod at a time. |
| ServiceMonitor | Off by default (`serviceMonitor.enabled`, needs the Prometheus Operator CRD); scrapes `/metrics`. |
| StatefulSet, headless Service, PVC | Postgres 18 pinned by digest, one pod, UID 999, read-only root filesystem, a 1Gi PVC on the default StorageClass. Off with `postgres.enabled: false`. |
| Job | `alembic upgrade head` with the app image, as an Argo CD `Sync` hook. |
| Job, ServiceAccount, Role, RoleBinding | Creates the database password Secret if it is missing, as Argo CD `PreSync` hooks. Off with `database.createSecret.enabled: false`. |

**Order ([ADR-0010](docs/adr/0010-migration-ordering.md)):** Argo CD sync waves run Postgres (`-1`), then the migration Job (`0`), then the app Deployment (`1`). Each wave waits for the previous one to be healthy, so a failed migration stops the sync before any new app pod starts.

**Database values:** `database` says how the app and the Job connect (host, port, name, user, Secret, pool size). `postgres` configures the Postgres server in the chart (image, storage, security context, resources); it reads the same user, name and Secret, so both sides always match. For an external database, set `postgres.enabled=false` and `database.host`; without a host the render fails.

**Credentials ([ADR-0011](docs/adr/0011-database-credentials.md)):**
- The password lives in a Secret named by `database.existingSecret` (default `release-notes-db`, key `password`), never in Git.
- A Job in the chart creates it with a random 32-character hex password if it is missing, as an Argo CD `PreSync` hook before Postgres starts. An existing Secret is kept.
- Kubernetes builds `DATABASE_URL` from it with `$(DATABASE_PASSWORD)`, so the password must be letters and digits only.
- Postgres applies the password only on its first start, so do not delete or recreate the Secret while the PVC is kept.
- For an external database or a Secret from elsewhere, set `database.createSecret.enabled: false` and create the Secret yourself.

**Connection budget:** (app pods + 1 surge pod + 1 pod still shutting down) x (`database.poolSize` + `database.maxOverflow`) + 1 migration Job must stay below `postgres.maxConnections` (200; the Postgres default of 100 is too tight for a rollout at full scale). App pods = `autoscaling.maxReplicas` with the HPA on, else `replicaCount`. With the defaults: (5 + 2) x 15 + 1 = 106. The chart checks this at render time and fails with the numbers when a combination does not fit.

### Validate the chart

Needs Helm, [kubeconform](https://github.com/yannh/kubeconform) and Podman (for chart-testing).

```bash
helm lint chart
for f in chart/ci/*-values.yaml; do
  helm template ci chart -f "$f" | kubeconform -strict -summary -schema-location default \
    -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
done
podman run --rm -v "$PWD":/work:Z -w /work \
  quay.io/helmpack/chart-testing:v3.15.0@sha256:54317f2d93730ea9ca1236e3d79cd95d74110b8d733b6ab124e5829209b5f4e4 \
  sh -c 'git config --global --add safe.directory /work && ct lint --charts chart --validate-maintainers=false --check-version-increment=false'
```

- `values.schema.json` rejects unknown keys and bad values, for example a typo in a key or `logLevel: info`.
- Render-time checks (`release-notes.validate`) reject combinations the schema cannot express: the connection budget, `minReplicas` above `maxReplicas`, and `database.host` set while the in-chart Postgres is still enabled.
- `chart/ci/` holds the test cases: the defaults, every optional feature on, and an external database.

### Install on kind

Argo CD is the deploy path; this is for trying the chart by hand. Every command names the kind cluster.

```bash
buildah build --layers -t release-notes:local .
podman save -o release-notes.tar localhost/release-notes:local
kind load image-archive release-notes.tar --name release-notes && rm release-notes.tar

kubectl --context kind-release-notes create namespace release-notes-test
kubectl --context kind-release-notes label namespace release-notes-test \
  pod-security.kubernetes.io/enforce=restricted
helm --kube-context kind-release-notes install release-notes chart -n release-notes-test \
  --set image.repository=localhost/release-notes --set image.tag=local

kubectl --context kind-release-notes -n release-notes-test port-forward service/release-notes 8080:80
```

Then open http://127.0.0.1:8080/ (`http`, not `https`). On WSL with a Windows browser, add `--address 0.0.0.0` to the port-forward.

- Plain Helm ignores the Argo CD hooks and waves and starts everything at once:
  - Postgres and the app wait in `CreateContainerConfigError` until the `release-notes-db-secret` Job has created the Secret.
  - The migration Job can fail once or twice with `failed to resolve host 'release-notes-postgres'` until Postgres is Ready, then succeeds.
  - Until the tables exist, the app can answer 500.
- A plain `helm upgrade` cannot change the existing migration Job (its pod template is immutable). Delete the Job first: `kubectl --context kind-release-notes -n release-notes-test delete job release-notes-migrate`.

## Repository layout

```
app/          FastAPI app: routes (api.py, health.py), rules (service.py), models, settings, metrics
app/static/   The UI: index.html, app.js, app.css (no build step; security headers in app/ui.py)
migrations/   Alembic migrations (expand-only, safe during a rolling update)
tests/        pytest suite
docs/adr/     Architecture decision records
scripts/      smoke-test.sh: container smoke test
chart/        Helm chart: app, Postgres, migration Job; ci/ holds the test values
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
| [0010](docs/adr/0010-migration-ordering.md) | Migration Job as an Argo CD Sync hook, ordered by sync waves |
| [0011](docs/adr/0011-database-credentials.md) | Database password Secret generated in the cluster by a PreSync Job; Kubernetes builds `DATABASE_URL` |
