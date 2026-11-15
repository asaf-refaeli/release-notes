# ADR-0004: Request handling: sync routes with sync SQLAlchemy

## Context
- FastAPI runs `async def` routes on a single event loop and `def` routes in a thread pool (40 threads by default).
- A blocking call inside `async def` blocks the event loop: every request on the pod waits, probes included.
- Every API request runs one short Postgres query. The SQLAlchemy connection pool (5 + 10 overflow per pod) limits concurrent DB work in either model.
- Traffic is low: an internal release-notes tool.
- The lifecycle work needs concurrency tests (two parallel publishes) against a real Postgres.

## Decision
Use sync SQLAlchemy 2.0 with psycopg 3, and `def` routes for anything that touches the database, because:
- Async brings no throughput gain here: requests would wait for a pool connection instead of a thread.
- Tests stay simple: a plain `TestClient`, sync fixtures, and plain threads for the concurrency tests. No `pytest-asyncio` or event-loop handling.
- It matches FastAPI's docs ("if you just don't know, use normal `def`") and the official full-stack template (sync Session, `def` routes).

Health checks:
- `/healthz/live` is `async def`. It does no I/O, so it runs on the event loop and answers even when every thread is busy; the kubelet does not restart a pod that is only busy.
- `/healthz/ready` is `def`. It runs a sync `SELECT 1`. When the thread pool is full, a slow readiness answer correctly takes the pod out of the Service.

## Alternatives considered
- Async everywhere (`create_async_engine`, psycopg async or asyncpg, `async def` routes): a waiting coroutine costs a few KB against about 1 MB per thread, so async wins with many concurrent waits (outbound API or LLM calls, websockets, thousands of open connections). Rejected because none of these apply, and it adds test complexity.
- Mixed (async engine for some routes, sync for others): rejected because it means two database stacks in one small app.

## Consequences
- Good: simple code and tests; a blocking call costs one thread, not the event loop.
- Bad: under heavy load the thread pool and the DB pool can saturate, so requests queue and readiness slows. Mitigation: more replicas through the HPA, tuned pool sizes, and Postgres `max_connections` kept above pods x pool size.
- Bad: moving to async later touches every DB call and test.
- Rule: no blocking calls inside `async def`. Ruff's `ASYNC` rules catch the common cases.
