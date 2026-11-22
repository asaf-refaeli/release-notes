# ADR-0016: Image build and publishing: Buildah, one image per commit on main, released by digest

## Context
- The same image runs the app and the migration Job (ADR-0009). Only an image that passed every check may reach GHCR.
- GHCR tags can be moved, so a tag alone does not prove which bytes run.
- The build should run without a Docker daemon, on a laptop, a hosted runner or a runner pod.

## Decision
- **Build:** rootless Buildah; Trivy scans a `podman save` file, so no container socket is needed.
- **Publish:** every merge to `main` pushes `release-notes:sha-<commit>` with skopeo, from the separate `push` job (ADR-0015).
- **Release:** the version tag is added to the parent commit's image with `skopeo copy --preserve-digests`: same digest, no rebuild.
- **Deploy:** the GitOps repo pins tag and digest; Kubernetes pulls by digest.

## Alternatives considered
- `docker build`: works on GitHub's runners, but needs the Docker daemon, which runs as root and is missing in runner pods on containerd clusters.
- `docker build` with `docker/build-push-action`: built-in cache and SBOM, but it needs the Docker daemon (root) and differs from the local build.
- BuildKit rootless (`buildx`): daemonless too and more features, but a different tool from the local Buildah build.
- Rebuild the image at release time: the released bytes would not be the tested ones.

## Consequences
- Good: the same build locally and in CI, and the deployed digest is the one that passed.
- Bad: no built-in layer cache or SBOM; each CI build starts cold.
- Bad: a release tags the parent's image, so the release commit itself (versions and changelogs only) is never built.
