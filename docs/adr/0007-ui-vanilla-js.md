# ADR-0007: UI: static files and plain JavaScript on the JSON API

## Context
- The assignment asks for "a minimal UI on top of" the API. Every app feature must be usable from it, the backend extensions included: create, list, edit a draft, publish, archive and the audit history of a release.
- The assignment grades the DevOps work, so the UI should add as little as possible to build, scan and explain. In the rollout step the footer version shows which version answered during a rolling update.
- The JSON API already exists and is tested; a second set of routes for the UI would duplicate it.
- Goals for the page: simple, modern, no full page reloads.

## Decision
Serve static files from `app/static/` with FastAPI's `app.frontend("/", directory=STATIC_DIR, fallback=None)`, and use plain JavaScript (an ES module with `fetch`) that calls the existing JSON API, because:
- No new dependency and no build step: no Node in CI or in the image, and the page is three small files that Trivy and Semgrep scan as they are.
- The UI is just another API client: it uses the same endpoints the tests cover and the reviewer reads.
- Same origin: no CORS, and relative URLs (`/api/releases`) work on localhost, behind the ingress and in prod without config.
- No page reloads: create, edit, publish and archive update the table and the release panel in place.

Security, set in `app/ui.py` and pinned by tests:
- A middleware adds `Content-Security-Policy: default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff` and `Cache-Control: no-cache` (the browser revalidates, so a deploy is visible on the next load).
- User text reaches the page only through `textContent`, never as HTML. A test fails if `app.js` uses `innerHTML`, `outerHTML`, `insertAdjacentHTML` or `document.write`, and another fails on inline scripts, `style=` or `on*=` attributes in `index.html` (the CSP would block them anyway).
- `fallback=None`: an unknown URL returns 404, not the page with 200, so broken links stay visible in logs and metrics.
- `STATIC_DIR` is built from the module's location, so the app serves the page from any working directory (the container).

## Alternatives considered
- Server-rendered templates (Jinja2): rejected because every action is a full page reload, and it adds a second set of HTML routes next to the JSON API.
- htmx with Jinja2 partials: no reloads and little JavaScript, but rejected because it adds a dependency (a vendored script plus Jinja2) and HTML-fragment routes that repeat what the JSON API already does.
- React or Vue with Vite (the FastAPI full-stack template's choice): rejected because it needs Node and `npm` in CI and in the image, a `node_modules` tree to scan, and CORS or a second server, for one table, one panel and one form.

## Consequences
- Good: no new dependency; the image and the pipeline do not change for the UI.
- Good: the page shows API errors as they are, so the API messages are written for people (they name the version and say what to do) and stay the single source of truth.
- Bad: pytest cannot run JavaScript. Tests cover serving, headers and static rules (no HTML writes, no inline code, every element id `app.js` looks up exists in `index.html`); the behaviour is checked by hand in a browser.
- Bad: `/docs` and `/redoc` are exempt from the CSP, because Swagger UI loads from a CDN and runs an inline script.
- Bad: the page shows the first 100 releases (the API's page limit); there is no paging yet.
- Next steps: Playwright end-to-end tests in CI; htmx if the UI grows into several screens.
