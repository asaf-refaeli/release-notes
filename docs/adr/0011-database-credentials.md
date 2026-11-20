# ADR-0011: Database credentials: generated Secret, URL built by Kubernetes

## Context
- The app, the migration Job and Postgres all need the same database password. Nothing secret may be in Git.
- The app reads one `DATABASE_URL` (`postgresql+psycopg://user:password@host:port/name`); only the password in it is secret. User, host, port and database name are plain chart values.
- The cluster is rebuilt from scratch by the gitops repo's `up.sh`, and its database starts empty each time.
- Argo CD renders the chart with `helm template` on every comparison, so a chart cannot generate a password itself: `randAlphaNum` changes on every render and `lookup` returns nothing.

## Decision
- `up.sh` creates one Secret per environment with a random password (`openssl rand -hex 16`), only if the Secret does not exist yet. The password is never printed, written to a file or committed; the repo holds the command, not the value.
- The chart only names the Secret (`database.existingSecret`, key `database.passwordKey`). Postgres reads it as `POSTGRES_PASSWORD`; the app Deployment and the migration Job read it as `DATABASE_PASSWORD`, and Kubernetes builds `DATABASE_URL` from it with `$(DATABASE_PASSWORD)`. User, database name and host come from the same `database` values on both sides, so they always match.
- Reasons: no app change; the rendered manifests and the Argo CD UI show only the Secret name and the placeholder; the chart works unchanged with any tool that creates the Secret.

## Alternatives considered
- Sealed Secrets or SOPS: the encrypted secret can live in Git, but decrypting it needs a key in the cluster. Every `up.sh` builds a new cluster with a new key, so the committed secret cannot be decrypted unless the key is backed up outside Git and restored, which is again a secret outside Git.
- External Secrets Operator with Vault or a cloud secret manager: the real-cluster answer. An `ExternalSecret` in the gitops repo makes the Secret GitOps-managed while the value stays in the store, trusted through the pod's cloud identity. Not used because kind has no secret store; switching adds one `ExternalSecret` and no chart change.
- The app builds the URL from separate fields (`sqlalchemy.URL.create`): handles any character in the password, but changes the settings, tests, smoke test and Alembic `env.py`, which all use `DATABASE_URL` today.
- The Secret holds the full URL: no app change, but `up.sh` would have to know the chart's Service name and namespace, and a chart rename would silently break the connection.

## Consequences
- Good: nothing secret in Git or in any rendered manifest; one source for the password on both sides.
- Bad: the Secret is created by a bootstrap script, not reconciled by Argo CD; a manual change to it is not detected or reverted.
- Bad: the password must be letters and digits only, because it sits inside a URL. `openssl rand -hex` guarantees it; a hand-made password with `@` or `/` would break the connection.
- Bad: Postgres applies the password only on its first start. If the Secret is recreated with a new password while the old volume is kept, Postgres keeps the old one and the app and migration Job fail with `password authentication failed`. Hence "create only if missing".
- Inside the cluster the password is readable by anyone allowed to read Secrets or `exec` into the pods (env vars), and etcd stores it unencrypted unless encryption at rest is on. Protection relies on RBAC.
