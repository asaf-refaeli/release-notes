# ADR-0013: Environments: one chart, two values files, two Applications

## Context
- The app needs separate settings for at least two environments without duplicating manifests.
- Everything runs on one local kind cluster, deployed by Argo CD from the `gitops` repo.
- One Argo CD Application renders one Helm release with one merged set of values, so one Application cannot run two environments.

## Decision
Two environments, dev and prod, both deployed, each in its own namespace (`release-notes-dev`, `release-notes-prod`):
- One chart (this repo). The environment differences live only in `gitops/workloads/apps/release-notes/values-dev.yaml` and `values-prod.yaml`: replicas and HPA, PDB, log level, resources, hostname, storage size.
- Two plain Application files that differ only in name, namespace and values file.
- Both environments run the same image. CI writes the new tag and digest to both values files in one commit, so one revert rolls both back. There is no promotion flow.
- Namespaces stand in for clusters. In production each environment would be its own cluster, and only the Application's `destination.server` would change.

Reasons:
- Both settings are proven by running, not only by rendering.
- Each environment syncs, fails and rolls back on its own.
- Adding an environment is one values file plus one Application file.

## Alternatives considered
- One Application with both values files: Helm merges them into one release, so only one environment would run and the other file would never be exercised.
- ApplicationSet with a list generator: one file generates both Applications. Fewer files, but one more concept and a template that can break every environment at once. Worth it from three or more environments.
- An umbrella chart that includes the chart twice: both environments in one sync, so they succeed or fail together.

## Consequences
- Good: the separation is visible in Git, in Argo CD and in the cluster.
- Bad: two copies of Postgres and the app on one laptop. The prod HPA (2 to 4) and replica counts are sized for an 8 GB machine, not from load tests.
- Bad: dev and prod get the same image at the same time; nothing gates prod on dev.
