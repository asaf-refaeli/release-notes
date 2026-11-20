# ADR-0009: One image for the app, the migration Job and the UI

## Context
- The service has three parts: the API, the static UI (ADR-0007) and the Alembic migrations.
- `migrations/env.py` imports `app.config` and `app.models`, so migrations need the app's code and packages.
- The migration Job must run before new pods start, and its schema must match the code those pods run.
- Each release is deployed by pinning one image tag + digest in the GitOps values.

## Decision
Build one image and run it with two commands:
- the app Deployment uses the default `CMD` (Uvicorn serving the API and the UI);
- the migration Job runs `alembic upgrade head` from the same image.

Because:
- One digest per release covers the API, the UI and the migrations, so the schema always matches the code that ships with it, and the UI always matches the API it calls.
- A separate migration image would hold almost the same contents: the migrations import the app.
- CI builds, scans and pushes one image, and the GitOps update writes one digest.
- It follows Twelve-Factor's "admin processes": one-off tasks like migrations run from the same release as the app.

## Alternatives considered
- Separate migration image (a second `--target` in the Dockerfile): rejected because it saves only Alembic and the migration files (about 1 MB) and adds a second digest that must stay in step with the app's.
- A separate migration tool (Flyway, Atlas): rejected because the migrations would be rewritten in SQL, losing the test that checks them against the models.
- Separate frontend image (nginx): rejected because the UI and the API would roll out separately, so a new page could call an old API; the security headers would move from tested Python into nginx config; and the UI would need path routing. It fits a UI with its own build step or served from a CDN.
- Migrations at app startup: rejected because several replicas would run them at the same time.
- The audit trail as its own service: rejected because a state change and its event are written in one transaction (ADR-0005). Across services that needs a transactional outbox, a broker and idempotent consumers.

## Consequences
- Good: one image, one digest, one scan per release; nothing to keep in step.
- Bad: the app image carries Alembic and the migration files. What a running pod can do to the schema depends on its database user, which is set with the chart's credentials.
