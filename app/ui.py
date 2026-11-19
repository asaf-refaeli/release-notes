"""The browser UI: where its files live and the security headers on every response."""

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Request, Response

STATIC_DIR = Path(__file__).parent / "static"

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)

# Swagger UI loads its JS and CSS from a CDN and runs an inline script,
# which the policy above would block. Exact paths, so nothing else skips the CSP.
DOCS_PATHS = {"/docs", "/docs/oauth2-redirect", "/redoc"}


async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-cache"
    if request.url.path not in DOCS_PATHS:
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response
