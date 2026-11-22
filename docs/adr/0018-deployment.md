# ADR-0018: Deployment: CI commits released versions to kind-gitops with a GitHub App

## Context
- Argo CD deploys from `kind-gitops`: the chart version in each Application, the image tag and digest in each values file.
- A workflow's `GITHUB_TOKEN` can only write to its own repo, and `kind-gitops` `main` requires pull requests.

## Decision
- After a release, the `update-gitops` job writes the new image tag and digest to both values files and the new chart version to both Applications, in one commit pushed to `kind-gitops` `main`.
- It authenticates as a GitHub App installed on `kind-gitops` only (Contents read and write), with a token that expires after an hour. The App bypasses the PR rule, not the force-push rule.
- The job runs no code from this repo and stages only the four files it edits.

## Alternatives considered
- Open a PR in `kind-gitops` for each deploy: a second approval after the release PR, with nothing new to review.
- Argo CD Image Updater: one more component in the cluster, while CI already knows the exact version and digest.

## Consequences
- Good: every deploy is one commit in `kind-gitops`, and reverting it is the rollback for both environments.
- Bad: the App's private key can mint write tokens for `kind-gitops`; it must be rotated if leaked.
- Bad: deploy commits skip review in `kind-gitops`; the review happened on the release PR.
