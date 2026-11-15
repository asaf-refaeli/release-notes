# ADR-0001: Git workflow: GitHub Flow

## Context
- Single developer.
- Every merge to `main` builds an image, pushes it to GHCR, and updates the dev and prod values in the GitOps repo, so `main` must always be deployable.
- Work comes in task-sized pieces (service skeleton, Dockerfile, chart, CI pipeline).
- Environment differences live in the GitOps repo (`values/dev.yaml`, `values/prod.yaml`), not in app branches.

## Decision
Use GitHub Flow because:
- CI runs on the PR before the merge, keeping broken code out of `main` and the cluster.
- Each task fits one branch (`feat/`, `fix/`, `ci/`, `chore/`, `docs/`) and one PR, squash-merged with a Conventional Commit title.
- `main` is protected by a ruleset: no direct pushes, CI required. The ruleset is added together with CI; before that, nothing runs on merge.

## Alternatives considered
- Trunk-Based Development (commit to `main`, or to branches that live less than a day): rejected because avoiding merge conflicts across many developers doesn't matter for a single developer, and unfinished work would need feature flags.
- GitFlow: rejected because it is built for versioned releases maintained in parallel, with long-lived `develop` and release branches.

## Consequences
- Good: each task is one PR with its diff and CI results in one place, `main` stays deployable.
- Bad: deploys happen per finished task, branches can drift from `main`, CI is the only merge gate (no approvals).
