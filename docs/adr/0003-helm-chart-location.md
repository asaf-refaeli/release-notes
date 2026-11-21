# ADR-0003: Helm chart location: application repository

## Context
- The app is deployed by Argo CD (GitOps) from a separate GitOps repo (`kind-gitops`) to two environments on kind.
- The Helm chart (app Deployment, Postgres StatefulSet, migration Job) needs a home: this repo or `kind-gitops`.
- Environment values and the deployed image tag live in `kind-gitops` either way.

## Decision
Keep the Helm chart in the application repository, and keep environment values, the deployed image tag and digest, and the Argo CD Applications in `kind-gitops`, because:
- Clear sources of truth: this repo defines how the app runs; `kind-gitops` defines what version and configuration is deployed where.
- Atomic changes: code and the chart changes it needs (probes, ports, env vars, migrations) are reviewed in one PR.
- CI validation: the chart is linted and rendered in the same pipeline as the code, before merge.
- Maintainability: the chart evolves with the code it deploys and doesn't drift.

## Alternatives considered
- Helm chart in the GitOps repository: centralizes all Kubernetes config and uses a single-source Argo CD Application, but rejected because app-related changes would need coordinated PRs across two repos.

## Consequences
- Good: one PR per feature, chart tested with the code, no CI loop since CI commits only the image tag and digest to `kind-gitops`.
- Bad: Argo CD needs a multi-source Application (chart from this repo, values from `kind-gitops`) or a published chart (e.g. OCI in GHCR).
- Bad: chart and image versions must be kept compatible, because `kind-gitops` pins the image while the chart comes from this repo.
