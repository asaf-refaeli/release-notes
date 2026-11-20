# ADR-0009: One image for the app, the migration Job and the UI

## Context
- The service has three parts: the API, the static UI (ADR-0007) and the Alembic migrations.
- `migrations/env.py` imports `app.config` and `app.models`, so the migrations need the app's code and packages.

## Decision
Build one image and run it with two commands: the app Deployment uses the default `CMD` (Uvicorn serving the API and the UI), and the migration Job runs `alembic upgrade head`. Neither part has a reason to be split out.

## Alternatives considered
- Separate migration image: rejected because it would contain the app's code and packages anyway (the migrations import them), so it would be a near-copy of the app image with nothing gained.
- Separate frontend image (e.g. nginx): the common choice when the UI has its own build step, its own team or release cadence, or is served from a CDN. None of these applies: the UI is four static files with no build step, served by the app (ADR-0007).

## Consequences
- Bad: the app pods carry Alembic and the migration files, which only the Job uses.
