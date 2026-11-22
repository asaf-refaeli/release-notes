# ADR-0012: Traffic entry: Traefik with Gateway API

## Context
- The app runs on a local kind cluster. Its nodes are Docker containers, so the browser and the rollout check script cannot reach a Service without a published port.
- The rollout check sends traffic during a rolling update and must count zero failures, so requests have to spread across pods and keep working while pods are replaced. `kubectl port-forward` attaches to one pod and breaks when that pod stops.
- Two environments (dev, prod) run on the same cluster.

## Decision
Traefik as the Gateway API controller, deployed by Argo CD. The platform owns a `GatewayClass` and one `Gateway` (`web`, namespace `traefik`) that accepts routes only from the app namespaces. The chart ships an `HTTPRoute` (`route.*` values) per environment: `dev.localhost` and `prod.localhost`. kind publishes host port 80 to Traefik's NodePort 30080. Reasons:
- Gateway API is the current Kubernetes standard for ingress traffic. Ingress is frozen, and its features beyond host and path are controller-specific annotations.
- It separates ownership: the platform owns the entry point (Gateway), and the app owns only its routing rule (HTTPRoute).
- A proxy balances per request across Ready pods, so traffic spreads evenly during a rollout.
- One port serves both environments by hostname. A new environment is a values file, not a new port mapping.

## Alternatives considered
- Ingress with Traefik (or another controller): works with the same setup and needs no CRDs, but the API is frozen and extras are annotations. ingress-nginx, the usual kind example, was retired upstream in 2026.
- NodePort on the app Service: no extra components. Rejected because there is one port per environment, each a kind port mapping fixed at cluster creation; kube-proxy balances per connection, not per request; and a keep-alive client (the rollout check) would hit the pod shutdown race itself instead of a proxy handling it.
- cloud-provider-kind (kind's documented LoadBalancer, Gateway and Ingress support): runs as a process on the host, outside Argo CD, and its container IPs may not be reachable from a Windows browser on WSL2.
- Envoy Gateway: the reference implementation, but needs extra configuration to pin a NodePort on kind, for no gain here.

## Consequences
- Good: production-like entry point; hostnames per environment; per-request load balancing; route status (`kubectl describe httproute`) explains a route that does not attach.
- Bad: two more Argo CD Applications (Gateway API CRDs, Traefik) and about 100 MiB of memory.
- Bad: the Gateway API CRD version must be one Traefik supports (pinned together).
- Bad: Traefik keeps pooled connections to the pods. Its idle timeout must stay below Uvicorn's keep-alive, or Traefik can send a request on a connection Uvicorn has just closed and return a 502. Traefik's default `idleConnTimeout` is 90 s ([ServersTransport](https://doc.traefik.io/traefik/reference/routing-configuration/http/load-balancing/serverstransport/)) and Uvicorn's is 5 s, so the image sets `--timeout-keep-alive 100` (ADR-0008). This is the rule Google Cloud and AWS give for their load balancers ([Google Cloud](https://docs.cloud.google.com/load-balancing/docs/https/troubleshooting-ext-https-lbs), [AWS](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-load-balancer-attributes.html)). The two values live in different repos: raising Traefik's timeout above 100 s brings the 502s back.
