# ADR-0015: CI job flow: checks first, then the image, then a separate push

## Context
- The checks on the source take about a minute; building, smoke-testing and scanning the image take a few minutes.
- A built image exists only on the runner that built it. The push needs `packages: write`, and the job that builds also runs PR code.

## Decision
- `lint`, `test`, `sast` and `helm` run in parallel. The `image` job needs the source checks: build, smoke test, Trivy.
- On `main`, the image is handed to a separate `push` job as an artifact. Only `push` has `packages: write`, and it runs no repository code.

## Alternatives considered
- Build in parallel with the checks: saves at most the length of the checks (about a minute), and the image hand-off costs most of that back.
- Build first, push a test tag to a separate package (`release-notes-ci`), and run the image tests as parallel jobs that pull it; the release copies the tested digest to `release-notes`. The shape to scale to, but every PR pushes an untested image and PR jobs need write access. Kept as the next step.
- Build and push in the same job: one job less, but PR code would run in a job that holds the push token.

## Consequences
- Good: a failing check never spends minutes on a build, and no PR job can write to the registry.
- Bad: the image result arrives about a minute after the checks.
- Bad: the image tests cannot be split across runners; moving to the registry hand-off fixes that when they grow.
