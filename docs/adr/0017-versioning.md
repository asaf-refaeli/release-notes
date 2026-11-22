# ADR-0017: Versioning: release-please with separate app and chart versions

## Context
- The app and the chart change independently. The app version lives in `pyproject.toml`, `uv.lock` and the chart's `appVersion`.
- `main` takes only squash merges with Conventional Commit titles (ADR-0001), so every commit says what kind of change it is.

## Decision
- release-please with two packages: the app (`python`) and the chart (`helm`). It keeps one release PR open; merging it creates the tags and GitHub Releases.
- release-please has no `uv.lock` updater, so the release job runs `uv lock` on the release PR branch and pushes the change.
- An app release tags the tested image (ADR-0016). A chart release publishes the chart to `oci://ghcr.io/asaf-refaeli/charts`.
- The gates skip the release PR and the release commit: they only change versions and changelogs.

## Alternatives considered
- Let release-please edit `uv.lock` itself (a JSONPath extra-file): tested. Only a fixed position works, and a new dependency would shift it and make it write another package's version.
- Never bump `pyproject.toml`: no lockfile problem, but a version field that is always wrong.
- Deploy the chart from git tags in this repo: works, but the chart would not be a versioned artifact like the image.

## Consequences
- Good: every version is written by a tool, in one release commit; image and chart are both versioned artifacts in GHCR.
- Bad: the release PR is opened by a bot, so its checks start only after "Approve workflows to run".
- Bad: the repo's `appVersion` can be newer than the one inside the last published chart; the GitOps repo always sets the image explicitly.
