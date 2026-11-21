# ADR-0008: Container image: Python on Alpine, non-root, read-only

## Context
- The same image runs as the app Deployment and as the database migration Job in the Helm chart; CI builds, smoke-tests and scans it.
- Kubernetes runs it as non-root, with a read-only root filesystem and all capabilities dropped, and gives it 30 s to stop during a rollout.
- Built with rootless Buildah 1.33.7, the same version locally and on GitHub's `ubuntu-24.04` runners.
- CI fails the build on any HIGH or CRITICAL finding from Trivy, so the base image decides whether that gate can pass at all.

## Decision
Two stages on `docker.io/library/python:3.14.10-alpine3.24` (tag + digest): the builder runs `uv sync --locked --no-dev`, the runtime copies the venv, `alembic.ini`, `migrations/` and `app/`, runs as `USER 10001`, and starts Uvicorn in exec form. Choices that need a reason:
- **Alpine as the base:** the official Python image on Alpine 3.24. Trivy 0.76.2 finds 0 HIGH/CRITICAL in the app image (51 on Debian slim, mostly in OS tools the app never runs and with no fix available yet); 130 MB instead of 208 MB.
  - Alpine uses musl instead of glibc. Every runtime dependency has a ready-made musl wheel for Python 3.14 (checked with `uv pip install --dry-run --python-platform x86_64-unknown-linux-musl --only-binary :all:`), so nothing is compiled; `psycopg[binary]` bundles its own Postgres client library.
  - musl's DNS resolver differs from glibc's (search domains, error handling, parallel queries). Checked on a kind cluster: from the pod, the Postgres Service resolves by short and full name, the app is Ready and serves the API and UI, and it starts in about the same time as on Debian.
- **`pyproject.toml` and `uv.lock` are copied in, not bind-mounted** (the uv docs use bind mounts): Buildah 1.33's layer cache ignores bind-mounted file contents, so a local rebuild after a dependency change reused the old install and skipped the `--locked` check (reproduced).
- **Bytecode compiled at build time**, the packages by uv (`UV_COMPILE_BYTECODE=1`) and the app and migrations by `python -m compileall`: Python cannot write its cache on a read-only disk.
- **pip removed:** unused at runtime and a common source of CVE findings.
- **Files owned by root, not `COPY --chown`:** the app can read its code but not change it.
- **`CMD`, not `ENTRYPOINT`:** the migration Job runs `alembic upgrade head` from the same image by replacing the command (one image for app, migrations and UI: ADR-0009).
- **`--timeout-graceful-shutdown 20`:** 20 s plus the 5 s preStop sleep stays under the 30 s grace period.
- **No `HEALTHCHECK`:** Buildah's default OCI format does not store it; Kubernetes probes do this job.
- `scripts/smoke-test.sh` checks the result on every build: non-root, migrations run, read-only with no `/tmp`, no capabilities, API and UI served, exit code 0 on SIGTERM.

## Alternatives considered
Base image (Trivy 0.76.2, HIGH/CRITICAL in the base image alone):
- Debian slim (`python:3.14.10-slim-trixie`), the previous base: 56 findings in the base, 51 in the app image, 1 of them fixable. Most are in OS tools the app never runs (`util-linux` mount helpers, `perl-base`) and unreachable under the hardened runtime, but no fix exists for 49, so the gate could only pass by ignoring unfixed findings. glibc matches the CI runner that runs pytest.
- Google distroless (`python3-debian13`): rejected; 90 findings and Python 3.13, the app needs 3.14.
- Chainguard (`cgr.dev/chainguard/python`): 0 findings, but the free tier only offers `latest`, which is already Python 3.15, so the Python version cannot be pinned.
- Docker Hardened Images (`dhi.io/python`): built for this case and pinnable, but pulling needs a Docker account login in CI and locally; not tested.
- uv's image (`ghcr.io/astral-sh/uv:python3.14-trixie-slim`): the official Python slim image plus uv. Fine for a builder, but the runtime does not need uv.
- Full `python:3.14` (used by the FastAPI full-stack template): rejected because it is much larger and ships compilers and many more packages to scan.

## Consequences
- Good: the strict Trivy gate passes; a stale lock fails the build; the image runs unchanged under the chart's securityContext; 130 MB, no build tools, no pip.
- Bad: pytest runs on the CI runner (glibc), not on musl. Differences between the two C libraries (DNS, compiled packages, locale details) show only in the tests that run the image: the smoke test and the E2E tests, plus the deployment on kind.
- Bad: DNS on musl is a known risk in clusters with unusual DNS setups (several upstream servers that disagree, servers that return errors for some search domains). The kind check covers this cluster, not every cluster.
- Bad: busybox replaces bash and coreutils, so `kubectl exec` into the pod gets a smaller `sh` toolset.
- Bad: the process runs with group 0 (`USER` names no group). That is the OpenShift convention and harmless here; the chart can set `runAsGroup`.
- Bad: Buildah stores images in Podman's store, not Docker's; loading one into kind takes `podman save` + `kind load image-archive`.
- Bad: the base images come from Docker Hub, which limits anonymous pulls; CI logs in or uses a mirror.
- Open: whether `APP_VERSION` is baked in at build time or set by the chart is decided with the release flow. The image defaults to `dev`.
