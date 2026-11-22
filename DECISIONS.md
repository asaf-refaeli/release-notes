# Decisions

Each decision links to its full record in `docs/adr/`. Proof of the rollout and rollback: [docs/verification.md](docs/verification.md).

## Decisions

| Area | Decision | ADR |
|---|---|---|
| Git workflow | GitHub Flow, Conventional Commit PR titles | [0001](docs/adr/0001-git-workflow.md) |
| CI platform | GitHub Actions | [0002](docs/adr/0002-ci-platform.md) |
| Repos | App repo + separate GitOps repo; the chart lives with the app | [0003](docs/adr/0003-helm-chart-location.md) |
| Request handling | Sync routes with sync SQLAlchemy; `/healthz/live` async | [0004](docs/adr/0004-request-handling-sync.md) |
| Concurrent writes | Row lock (`SELECT ... FOR UPDATE`) plus a partial unique index | [0005](docs/adr/0005-concurrent-writes.md) |
| Tests | A real Postgres through testcontainers | [0006](docs/adr/0006-tests-on-real-postgres.md) |
| UI | Static files and plain JavaScript on the JSON API, strict CSP | [0007](docs/adr/0007-ui-vanilla-js.md) |
| Container image | Python on Alpine, non-root, read-only; Uvicorn keep-alive above Traefik's | [0008](docs/adr/0008-container-image.md) |
| One image | Same image for the app, the migration Job and the UI | [0009](docs/adr/0009-one-image.md) |
| Migrations | Argo CD Sync hook and sync waves: DB, then migration Job, then app; expand-only | [0010](docs/adr/0010-migration-ordering.md) |
| DB credentials | Secret generated in the cluster by a PreSync Job; no secret in Git | [0011](docs/adr/0011-database-credentials.md) |
| Traffic entry | Traefik with Gateway API, HTTPRoute per environment | [0012](docs/adr/0012-traffic-entry.md) |
| Environments | One chart, two values files, two Applications, same image | [0013](docs/adr/0013-environments.md) |
| GitOps layout | App of apps, self-managed Argo CD, two AppProjects | [0014](docs/adr/0014-gitops-layout.md) |
| CI job flow | Checks first, then the image, then a separate push job | [0015](docs/adr/0015-ci-job-flow.md) |
| Image build | Buildah, one image per commit on `main`, released by digest | [0016](docs/adr/0016-image-build-and-publishing.md) |
| Versioning | release-please, separate app and chart versions | [0017](docs/adr/0017-versioning.md) |
| Deployment | CI commits released versions to `kind-gitops` with a GitHub App | [0018](docs/adr/0018-deployment.md) |
| Zero-downtime rollout | RollingUpdate `maxUnavailable: 0`, readiness on the DB, preStop sleep, graceful shutdown; proven with `scripts/rollout_check.py` | [0008](docs/adr/0008-container-image.md), [0010](docs/adr/0010-migration-ordering.md) |
| Rollback | `kind-gitops/scripts/rollback.sh` reverts the deploy commit through a PR; the code revert is a normal PR here | [0018](docs/adr/0018-deployment.md) |

## Rollout failures on a real cluster

- **A bad version that passes the checks.** Readiness and `minReadySeconds: 5` pass, the rollout completes, and the
  errors start later. Nothing rolls back automatically: Argo CD only reports `Healthy`. Detection is the checker and
  alerts; recovery is `rollback.sh`. Real cluster: progressive delivery with automated analysis (Argo Rollouts) and
  alerts on the error rate.
- **Readiness passes before the schema exists.** `/healthz/ready` checks only `SELECT 1`, so a pod can serve before a
  migration it needs has run. The migration Job runs first (ADR-0010), but the probe cannot prove it. Real cluster: a
  schema-aware readiness check or a PostSync smoke test.
- **A failed migration blocks the release.** The sync stops before any new pod starts, and old pods keep serving. The
  release is stuck until a fix ships. A rollback across a migration also fails, because the old image does not know
  the newer Alembic revision. Real cluster: a migration Job that skips an unknown revision, drilled before it ships.
- **Connection budget exhausted during the surge.** The new pod opens its own pool while old pods still hold theirs. If
  the budget is exceeded, the new pod cannot connect, fails readiness, and the rollout stalls. The chart checks the
  budget at render time; PgBouncer is the real-world answer.

## Scaling path

The pipeline builds once and runs everything on that image. This is the shape it moves to when it outgrows that.

- **Trigger:** E2E tests pass about 5 minutes and need splitting, or more jobs need the image.
- **Change:** build first and push a test tag to a separate package (`release-notes-ci:sha-<commit>`). Smoke, E2E and
  Trivy run as parallel jobs that pull that tag. The release copies the tested digest without a rebuild.
- **Cost:** `packages: write` on PR jobs, untested images in a registry, and a scheduled cleanup of test tags.
- **E2E sharding:** split the suite into a matrix of shards (the FastAPI template uses 4).

## Roadmap

- **E2E tests:** Python Playwright against the built image, covering every UI feature and the style checks.
- **Load testing with k6:** parallel users and latency thresholds, in CI after each deploy.
- **Post-deploy write check:** a PostSync Job in dev that creates a release, reads it back and checks its event.
- **Rollback across a migration:** the migration Job skips an unknown revision (option A), after a drill on dev.
- **Registry mirror:** pull-through cache for GHCR.
- **Postgres operator (CloudNativePG):** replicas, failover, backups and upgrades for the database, instead of one
  hand-managed pod.
- **Superuser app connection:** an unprivileged owner role (CloudNativePG creates one).
- **Database Secret not reconciled:** External Secrets Operator (ADR-0011).
- **StatefulSet forced rollback:** delete a never-Ready Postgres pod by hand after a revert.
- **"Synced/Healthy" is not "done":** readiness probe or the PostSync check.

### App
- **Discard feature:** a draft can be discarded (soft delete) instead of deleted, because the audit trail
  keeps its history. It adds a `DISCARDED` status, which the list hides.
- **Confirm one-way actions:** Publish and Archive ask first in a small dialog, since neither can be undone.
- **Record what an edit changed:** a nullable `changes` column on audit events (expand-only migration), so the history
  shows "Version changed from 1.5.0 to 1.5.1".
- **Suggested version:** the New release dialog suggests the next version after the newest published one.
- **Warn on an existing version:** the dialog warns when another release already uses the version, before saving.