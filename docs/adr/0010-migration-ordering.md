# ADR-0010: Migration ordering: Argo CD Sync hook and sync waves

## Context
- One Helm chart holds Postgres, the migration Job (`alembic upgrade head`, same image as the app, ADR-0009) and the app Deployment.
- On a first install the order must be: Postgres ready, then the migration, then the app. On an upgrade the migration must finish before new pods serve. Migrations are expand-only, so old pods keep working on the new schema.
- Helm applies all normal resources of a release at once; it can only order resources by making them hooks.
- Argo CD is the only deploy path: the `kind-gitops` repo syncs this chart to every environment. CI validates the chart (lint and schema) but does not install it.

## Decision
Run the migration Job as an Argo CD `Sync` hook (`hook-delete-policy: BeforeHookCreation`), ordered by sync waves: Postgres StatefulSet `-1`, migration Job `0`, app Deployment `1`. Argo CD waits for each wave to be healthy before the next one. Reasons:
- No extra code: ordering is a few annotations.
- The migration shows as its own step in the Argo CD UI, and a failed migration fails the sync before any new pod is created; the old pods keep serving.
- A Job's pod template cannot be changed once created. As a hook, Argo CD deletes and recreates the Job on every sync, so a new image never hits that limit.
- This is the setup the Apache Airflow chart documents for Argo CD users.

## Alternatives considered
- Helm hooks (`pre-upgrade` + `post-install`): the usual choice for plain Helm when the database lives outside the chart. Rejected because Argo CD maps them onto its own phases: `pre-upgrade` becomes PreSync, which runs before the Postgres StatefulSet exists on a first install, and `post-install` becomes PostSync, which runs only after the app is already serving.
- Plain Job (name changes with the image) plus a wait-for-migrations initContainer in every app pod (Airflow's default, GitLab): ordering lives in the chart, so it works the same under `helm install`, Flux and Argo CD, and can be tested in CI with `ct install`. Not chosen because it needs a schema check in the app that must also accept a newer database after a rollback, and extra CI plumbing, while there is only one deploy path.
- Migrate inside each pod (initContainer or at app startup): rejected because every new pod would race to run the same migration (Alembic has no lock) and it splits the one migration Job into many.

## Consequences
- Good: no code to maintain; a failed migration is a clear, early signal in Argo CD.
- Bad: the ordering holds only under Argo CD. A plain `helm install` or Flux ignores the annotations and starts everything together (the Job retries until the database is up; the app can answer 500 until the tables exist), and `helm upgrade` with a new image fails because the Job is immutable.
- Bad: CI does not test the ordering; the first real check is a sync to the dev environment.
- Next step if the chart is ever installed by another tool or tested with `ct install`: switch to the plain Job plus the wait-for-migrations initContainer.
