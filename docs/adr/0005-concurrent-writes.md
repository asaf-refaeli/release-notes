# ADR-0005: Concurrent writes: row lock plus a partial unique index

## Context
- The assignment requires data consistency "when concurrent requests attempt to update the same release".
- Every lifecycle write is "check a rule, then change": edit and publish need DRAFT, archive needs PUBLISHED. Two requests can both pass the check before either commits.
- Publishing also needs a unique version among published and archived releases. That rule spans two different rows (two drafts with the same version), so a lock on one row cannot enforce it.
- Each change and its audit event must be saved in the same transaction.
- Conflicts are rare: a small internal tool, and two writes to the same release at the same moment are unusual.

## Decision
Use a pessimistic row lock for rules on one release, and a database constraint for the rule across releases, because:
- `SELECT ... FOR UPDATE` in `_lock_release` (every edit, publish and archive starts with it) makes a second writer on the same row wait until the first commits, then read the committed row. The rule check then sees the real state.
- The partial unique index `uq_releases_version_published` (`version` unique `WHERE status <> 'DRAFT'`) makes Postgres refuse a second published version, however close in time. The service maps that `IntegrityError` to `409 DuplicateVersion`.
- Rules stay as plain Python checks that raise specific errors, so each failure gets its exact code (404, 409, 400).
- One transaction per action: lock, check, change, insert the event, commit.

Evidence (`tests/test_concurrency.py`): with `FOR UPDATE` removed, the double-publish test fails every run (`['ok', 'ok']`), and the edit-versus-publish test records an edit after publish. With the lock, both pass. The same-version test passes without the lock, because the index protects it.

## Alternatives considered
- Atomic conditional update (`UPDATE releases SET status='PUBLISHED' WHERE id=:id AND status='DRAFT'`, then check the row count): no lock and no wait. Rejected because a count of 0 does not say why (unknown id, wrong state, blank description), so the API cannot return the right code without extra queries, and the rules move into SQL.
- Optimistic concurrency (a `version` column checked on update, retry or 409 on mismatch; the Kubernetes `resourceVersion` model): best when conflicts are rare and reads dominate. Rejected because it adds a column, a migration, client retry handling and a new 409 meaning, for conflicts this app almost never has.
- `SERIALIZABLE` isolation: Postgres detects conflicting transactions and aborts one. Rejected because every write would need a retry loop for serialization failures.
- An application-level check for duplicate versions (a `SELECT` before publish): rejected because two requests can both see "no published 2.0.0" and both publish; only a constraint closes that race.

## Consequences
- Good: simple, readable code; exact HTTP codes; correctness proven by tests that fail without the lock.
- Good: the database enforces the cross-row rule, so it holds for any future code path.
- Bad: a second writer on the same release waits for the first transaction. Transactions are short, and `release_lock_wait_seconds` measures the wait.
- Bad: a transaction that stays open while holding the lock blocks other writers on that release. Rule: end every transaction promptly (the no-op PATCH rolls back at once for this reason).
- Next step if write contention grows: optimistic concurrency with a `version` column.
