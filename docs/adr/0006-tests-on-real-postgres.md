# ADR-0006: Testing: a real Postgres through testcontainers

## Context
- The assignment asks for "tests that mean something" covering business rules, state transitions, concurrency and audit trail consistency.
- The correctness of the service lives partly in Postgres: the row lock (`SELECT ... FOR UPDATE`), CHECK constraints, the partial unique index on published versions, server-side timestamps, and transactions that commit or roll back as one.
- The concurrency tests need two real connections committing at the same moment, and the rollback test needs a real constraint to fail.
- Migrations must produce exactly the schema the models describe.

## Decision
Run the whole suite against a real Postgres 18 started by [testcontainers](https://testcontainers.com/), because:
- Locks, constraints, partial indexes and isolation behave exactly as in production. The concurrency tests fail when the lock is removed, which proves they test Postgres behaviour and not a stand-in.
- The schema comes from `alembic upgrade head`, the same path as a deployment, and a test compares it with the models (`compare_metadata`), so migration drift fails the build.
- One container per test run keeps it fast: about 10 seconds for the full suite.

Setup (`tests/conftest.py`):
- One container and one `alembic upgrade head` per run (session-scoped fixtures).
- Before each test, `TRUNCATE ... RESTART IDENTITY CASCADE` empties every table and resets ids.
- The app is pointed at the test database by overriding the `get_engine` dependency.

## Alternatives considered
- SQLite in memory: fast and needs no Docker. Rejected because it has no `SELECT ... FOR UPDATE`, different types and constraint handling, and no real concurrent writers, so the tests that matter most would pass while proving nothing.
- Mocking the database session: rejected because it tests the mocks, not the rules the database enforces.
- A shared local or dev Postgres: rejected because tests then depend on manual setup and leftover state, and runs can interfere with each other.
- Rolling back a transaction after each test, instead of truncating: faster cleanup, but rejected because the concurrency tests commit from separate sessions, which a per-test rollback cannot undo.

## Consequences
- Good: tests prove behaviour that only a real database has; migrations are tested on every run.
- Good: the same suite runs locally and in CI with no extra setup beyond Docker.
- Bad: Docker is required to run the tests, and the first run pulls the `postgres:18` image.
- Bad: slower than an in-memory database, and sensitive to a slow Docker host (seen once when the WSL machine ran out of memory).
