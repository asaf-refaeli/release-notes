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

### Load balancer timers

- **Issue:** On kind, the only proxy is Traefik, and its timers are known and set in this repo. A cloud load balancer
  sits in front with its own timers, and some are fixed: Google's backend keep-alive is 600 s, AWS ALB's idle timeout
  defaults to 60 s. The keep-alive value chosen on kind cannot be copied to a cloud cluster. During a rollout, pods
  closing their connections make the resulting 502s more likely.
- **How I would handle it:** Read the load balancer's idle timeout and backend keep-alive first. Set the app's
  keep-alive above that value, and Traefik's (or the ingress controller's) below it. Keep the numbers in one place with
  a comment and an ADR, and test under steady traffic with the checker before trusting them.

### Shutdown outside the cluster

- **Issue:** The 5 s preStop sleep proven on kind covers Kubernetes and Traefik only. A cloud load balancer removes a pod
  on its own schedule, with a deregistration delay Kubernetes does not control. The kind margin says nothing about a
  cloud cluster's timing. Every rolling update terminates old pods, so a too-short sleep shows up as failed requests
  during the rollout.
- **How I would handle it:** Measure the load balancer's deregistration delay, not only Kubernetes' endpoint removal.
  Set the preStop sleep above it, or use a readiness gate so the load balancer marks the pod unhealthy before shutdown.
  Confirm with the checker during a real rollout.

### Capacity and disruption around the app

- **Issue:** A real cluster has several nodes, a cluster autoscaler, node drains for upgrades, and PDBs that compete with
  rollouts. kind has one fixed node with no drains, so a drain or a node loss during a rollout cannot happen there. A
  full node can still stall a surge pod on kind, under load. During a rollout, a pod with no free node stays Pending and
  the rollout stops, and a drain at the same time can remove a pod before its replacement is Ready.
- **How I would handle it:** Run the cluster autoscaler and keep spare capacity for the surge pod. Check the PDB before
  any node drain, and schedule node upgrades so they do not overlap with a release. Use a managed database so a node
  drain does not take the only database pod down, and every app pod with it.

### Observability after the rollout

- **Issue:** The checker runs for a few minutes and sees only its own window. Metrics-server reports CPU and memory only.
  The app already exposes request counts and latency at `/metrics`, but Prometheus is not installed and the
  ServiceMonitor is off, so nothing alerts on a failure after the checker stops. A rollout can finish green in Argo CD
  and still start failing minutes later, with nothing to say it is time to run `rollback.sh`.
- **How I would handle it:** Install Prometheus (kube-prometheus-stack) and enable the ServiceMonitor to scrape
  `/metrics`. Alert on the 5xx rate and latency for the release-notes Service, and watch those alerts during each
  rollout so a later failure can be traced to the release.

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
- **DAST:** a nightly OWASP ZAP API scan driven by `/openapi.json`, against the released image running with Postgres,
  plus a Trivy rescan of the deployed digest for newly published CVEs.
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