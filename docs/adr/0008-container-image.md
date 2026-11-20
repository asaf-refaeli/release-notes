# ADR-0008: Container image: Python slim, non-root, read-only

## Context
- The same image runs as the app Deployment and as the database migration Job in the Helm chart; CI builds, smoke-tests and scans it.
- Kubernetes runs it as non-root, with a read-only root filesystem and all capabilities dropped, and gives it 30 s to stop during a rollout.
- Built with rootless Buildah 1.33.7, the same version locally and on GitHub's `ubuntu-24.04` runners.

## Decision
Two stages on `docker.io/library/python:3.14.10-slim-trixie` (tag + digest): the builder runs `uv sync --locked --no-dev`, the runtime copies the venv, `alembic.ini`, `migrations/` and `app/`, runs as `USER 10001`, and starts Uvicorn in exec form. Choices that need a reason:
- **Debian slim as the base:** the official Python image, slim (no compilers or extra tools), on Debian 13 (trixie), the current stable. Every dependency installs as a ready-made glibc wheel (`psycopg[binary]` bundles its own Postgres client library), so nothing is compiled or installed with `apt-get`.
- **`pyproject.toml` and `uv.lock` are copied in, not bind-mounted** (the uv docs use bind mounts): Buildah 1.33's layer cache ignores bind-mounted file contents, so a local rebuild after a dependency change reused the old install and skipped the `--locked` check (reproduced).
- **Bytecode compiled at build time**, the packages by uv (`UV_COMPILE_BYTECODE=1`) and the app and migrations by `python -m compileall`: Python cannot write its cache on a read-only disk.
- **pip removed:** unused at runtime and a common source of CVE findings.
- **Files owned by root, not `COPY --chown`:** the app can read its code but not change it.
- **`CMD`, not `ENTRYPOINT`:** the migration Job runs `alembic upgrade head` from the same image by replacing the command (one image for app, migrations and UI: ADR-0009).
- **`--timeout-graceful-shutdown 20`:** 20 s plus the 5 s preStop sleep stays under the 30 s grace period.
- **No `HEALTHCHECK`:** Buildah's default OCI format does not store it; Kubernetes probes do this job.
- `scripts/smoke-test.sh` checks the result on every build: non-root, migrations run, read-only with no `/tmp`, no capabilities, API and UI served, exit code 0 on SIGTERM.

## Alternatives considered
Base image:
- Google distroless: rejected because its Python is Debian's 3.11 and the app needs 3.14.
- Alpine (`python:3.14-alpine`): smaller, but rejected because it uses musl instead of glibc, so some packages have no ready-made wheels or behave differently.
- uv's image (`ghcr.io/astral-sh/uv:python3.14-trixie-slim`): the official Python slim image plus uv. Fine for a builder, but the runtime does not need uv, so plain slim is used for both stages.
- Full `python:3.14` (used by the FastAPI full-stack template): rejected because it is much larger and ships compilers and many more packages to scan.

## Consequences
- Good: a stale lock fails the build; the image runs unchanged under the chart's securityContext; 218 MB, no build tools, no pip.
- Bad: the process runs with group 0 (`USER` names no group). That is the OpenShift convention and harmless here; the chart can set `runAsGroup`.
- Bad: Buildah stores images in Podman's store, not Docker's; loading one into kind takes `podman save` + `kind load image-archive`.
- Bad: the base images come from Docker Hub, which limits anonymous pulls; CI logs in or uses a mirror.
- Open: whether `APP_VERSION` is baked in at build time or set by the chart is decided with the release flow. The image defaults to `dev`.
