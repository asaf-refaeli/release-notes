# ADR-0014: GitOps layout: app of apps, self-managed Argo CD, two projects

## Context
- The `kind-gitops` repo must bring a clean kind cluster to a running system with one command (`scripts/up.sh`), and everything after the bootstrap should come from Git.
- Argo CD cannot install itself, so something imperative has to start it.
- Besides the app, the cluster needs platform components: Gateway API CRDs, Traefik and metrics-server (for the HPA), plus Argo CD itself.

## Decision
- **Bootstrap:** `scripts/bootstrap.sh` runs `helm install` for Argo CD once, then applies one root Application. These are the only imperative steps. The DB Secret is created in the cluster by the chart (ADR-0011).
- **App of apps with plain Application files:** root syncs `bootstrap/`. That folder holds two AppProjects and one Application file per component: argocd, gateway-api, traefik, metrics-server, release-notes-dev, release-notes-prod. Root sits inside the folder it syncs, so it is managed from Git too.
- **Order by sync waves between Applications:** projects `-1`, then argocd and gateway-api `0`, then traefik and metrics-server `1`, then the app `2`. An Argo CD health check for `Application` makes each wave wait until the previous one is Healthy.
- **Self-managed Argo CD:** the `argocd` Application points at the same wrapper chart (`workloads/platform/argocd`), with the same release name, that the bootstrap installed. It adopts the install, so Argo CD upgrades and config changes are commits. It has no cascade-delete finalizer, so deleting the Application never deletes Argo CD.
- **Two AppProjects:**
  - `platform`: this repo only. Its destinations are argocd, traefik and kube-system, with an explicit list of allowed cluster-scoped kinds.
  - `release-notes`: the app repo and this repo, the two app namespaces only, and no cluster-scoped kinds except Namespace.
  - Root stays in `default`, the only project that exists at bootstrap.
- **Platform charts are wrapper charts:** a `Chart.yaml` dependency plus `values.yaml`. The version is pinned once and read by both the bootstrap and the Application.

## Alternatives considered
- ApplicationSet (a git directory generator, as in the previous project): no file per component, but every component gets the same template and loses its own sync wave. Four components do not need a generator.
- Argo CD installed outside Git (Helm or Terraform only): simpler, but Argo CD's version and config would change by hand. That was the caveat in the previous project.
- Everything in the `default` project: one file less, but `default` allows any repo, namespace and kind. The app would get no isolation.
- Installing the platform charts straight from their Helm repos (no wrapper): fewer files, but the Argo CD version would be written in both the script and the Application.

## Consequences
- Good: after `up.sh`, every change to the platform or the app is a commit. Argo CD shows the whole cluster in one tree.
- Good: the app's project cannot deploy outside its namespaces or create cluster-wide resources.
- Bad: root and the `platform` project are admin-level by nature, because root can create Applications in any project and `platform` manages Argo CD itself. Push access to `kind-gitops` must be restricted.
- Bad: a bad Argo CD config committed to Git can stop Argo CD, and then nothing applies the fix. The break-glass is a manual `helm upgrade` with good values.
- Bad: the waves depend on the custom Application health check. Without it, a wave waits only for the child Application to be created.
