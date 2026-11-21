# ADR-0011: Database credentials: Secret generated in the cluster, URL built by Kubernetes

## Context
- The app, the migration Job and Postgres all need the same database password. Nothing secret may be in Git.
- The app reads one `DATABASE_URL` (`postgresql+psycopg://user:password@host:port/name`); only the password in it is secret. User, host, port and database name are plain chart values.
- The cluster is rebuilt from scratch by the gitops repo's `up.sh`, and its database starts empty each time. Argo CD is the only deploy path, and everything after its own install should come from Git.
- Argo CD renders the chart with `helm template` on every comparison, so the chart cannot render a password itself: `randAlphaNum` changes on every render and `lookup` returns nothing.

## Decision
- A Job in the chart creates the Secret inside the cluster if it is missing. It runs as an Argo CD `PreSync` hook, before the Sync phase starts Postgres. Its ServiceAccount, Role and RoleBinding are PreSync hooks one wave earlier. The Role allows `get` on that one Secret and `create` on Secrets in the namespace. The Job runs `kubectl` from a small pinned image (`alpine/kubectl`, tag + digest) as the app's non-root user, under Pod Security `restricted`.
- The password is 16 random bytes as 32 hex characters, generated in the pod. It is never printed, written to a file, committed or rendered; the repo holds the command, not the value. The Secret is created by the Job, not rendered by the chart, so Argo CD never tracks, diffs or prunes it.
- An existing Secret is never changed, so a re-sync keeps the password Postgres already uses.
- The chart names the Secret (`database.existingSecret`, key `database.passwordKey`). Postgres reads it as `POSTGRES_PASSWORD`; the app Deployment and the migration Job read it as `DATABASE_PASSWORD`, and Kubernetes builds `DATABASE_URL` from it with `$(DATABASE_PASSWORD)`. User, database name and host come from the same `database` values on both sides, so they always match.
- `database.createSecret.enabled` turns the Job off when the Secret comes from elsewhere. It must be off with an external database (`database.host`), and the render fails otherwise: a random password is useless for a database the chart does not run.
- Reasons:
  - The gitops bootstrap creates nothing but Argo CD and the root Application.
  - A new environment gets its Secret with no script change.
  - The password never leaves the cluster.
  - No app change.

## Alternatives considered
- **The bootstrap script creates the Secret** (`openssl rand -hex 16` before applying the root Application). Simplest, with no RBAC or extra image in the chart. But it is an imperative step outside Git, every new environment needs a script change, and the namespace must also be created by the script before Argo CD exists to create it.
- **A separate per-environment config Application** that holds the namespace, the same Job and later quotas and NetworkPolicy. It separates platform-owned setup from the app, but doubles the Applications and needs kustomize overlays for one Job. The next step once a platform team owns namespaces.
- **Sealed Secrets or SOPS:** the encrypted secret can live in Git, but decrypting it needs a key in the cluster. Every `up.sh` builds a new cluster with a new key, so the committed secret cannot be decrypted unless the key is backed up outside Git and restored, which is again a secret outside Git.
- **External Secrets Operator with Vault or a cloud secret manager:** the real-cluster answer. An `ExternalSecret` in the gitops repo makes the Secret GitOps-managed while the value stays in the store, trusted through the pod's cloud identity. Not used because kind has no secret store. Switching means one `ExternalSecret` plus `database.createSecret.enabled: false`, with no template change.
- **The app builds the URL from separate fields** (`sqlalchemy.URL.create`): handles any character in the password, but changes the settings, tests, smoke test and Alembic `env.py`, which all use `DATABASE_URL` today.
- **The Secret holds the full URL:** no app change, but whoever creates it must know the chart's Service name and namespace, and a chart rename would silently break the connection.

## Consequences
- Good: nothing secret in Git or in any rendered manifest; one source for the password on both sides; no imperative Secret step.
- Bad: the chart has a pod with permission to create Secrets in its namespace. That pod is the only one with a ServiceAccount token, and it runs only during a sync.
- Bad: one more image to pin, scan and update (`alpine/kubectl`, a community image; the official `registry.k8s.io/kubectl` has no shell).
- Bad: the ordering relies on Argo CD hooks. A plain `helm install` starts the Job together with Postgres, which waits in `CreateContainerConfigError` until the Secret exists, then starts.
- Bad: the Secret is not reconciled. A manual change to it is not detected or reverted, and deleting it while the PVC is kept makes the next sync generate a new password that Postgres does not know: the app and migration Job fail with `password authentication failed`.
- Bad: the password must be letters and digits only, because it sits inside a URL. The Job guarantees it; a hand-made password with `@` or `/` would break the connection.
- Inside the cluster the password is readable by anyone allowed to read Secrets or `exec` into the pods (env vars), and etcd stores it unencrypted unless encryption at rest is on. Protection relies on RBAC.
