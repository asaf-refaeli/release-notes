# Decisions

Each choice links to its full record in `docs/adr/`. This file is the list of what the setup does not protect against.
The decisions table and next steps are added at the end of the assignment.

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

## Future work

- **Discard feature (step 10):** a draft can be discarded (soft delete) instead of deleted, because the audit trail
  keeps its history. It adds a `DISCARDED` status, which the list hides.


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
