# ADR-0005: Concurrent writes: row lock plus a partial unique index

## Context
- The assignment requires consistency "when concurrent requests attempt to update the same release".
- Every lifecycle write checks a rule, then changes the row. Two requests can both pass the check before either saves.
- "No two published versions are the same" spans two rows, so locking one row cannot enforce it.

## Decision
- Every edit, publish and archive first locks the release row (`SELECT ... FOR UPDATE`). A second request on the same
  release waits, then sees the saved state and gets a 409.
- A partial unique index (`version` unique where `status <> 'DRAFT'`) makes Postgres refuse a duplicate published
  version. The app returns 409.
- Lock, check, change and the audit event are one transaction.

Proof: `tests/test_concurrency.py` fails every run with the lock removed.

## Alternatives considered
- Conditional `UPDATE ... WHERE status='DRAFT'`: no lock, but a 0-row result does not say why, so the API cannot
  return the right error.
- Optimistic locking (a `version` column): an extra column and client retries, for conflicts this app rarely has.
- `SERIALIZABLE` isolation: every write needs a retry loop.

## Consequences
- Good: simple code, exact error codes, the database enforces the cross-row rule.
- Bad: a second writer waits for the first; `release_lock_wait_seconds` measures it.
