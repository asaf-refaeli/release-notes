import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ui import CONTENT_SECURITY_POLICY, STATIC_DIR

# Medium, not small: the tests read the static files from disk.
pytestmark = pytest.mark.medium

client = TestClient(app)


def test_root_serves_html_with_security_headers():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Release Notes" in response.text
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-cache"


def test_docs_has_no_csp():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers


@pytest.mark.parametrize("path", ["/docs-guide", "/redocumentation", "/docs/other"])
def test_csp_exemption_is_only_the_docs_pages(path):
    # Only the exact Swagger/ReDoc pages skip the CSP, not paths that look like them
    response = client.get(path)

    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


def test_unknown_path_returns_404():
    # A browser address bar sends Accept: text/html; a fallback would serve the page
    response = client.get("/releasez", headers={"Accept": "text/html"})

    assert response.status_code == 404


def test_frontend_served_from_any_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    response = client.get("/")

    assert response.status_code == 200


def test_static_assets_served():
    js = client.get("/app.js")
    css = client.get("/app.css")

    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]


def test_js_never_writes_html():
    # User text must reach the page only through textContent (XSS)
    source = (STATIC_DIR / "app.js").read_text()

    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert sink not in source


def test_html_has_no_inline_code():
    # The CSP blocks inline scripts, style attributes and on* handlers
    html = (STATIC_DIR / "index.html").read_text()

    assert re.search(r"<script(?![^>]*\ssrc=)", html) is None
    assert re.search(r"\sstyle=", html) is None
    assert re.search(r"\son[a-z]+=", html) is None


def test_js_ids_exist_in_html():
    # An id renamed in only one file silently breaks that part of the page
    js = (STATIC_DIR / "app.js").read_text()
    html = (STATIC_DIR / "index.html").read_text()

    used_ids = re.findall(r'querySelector\("#([\w-]+)"\)', js)

    assert used_ids
    for element_id in used_ids:
        assert f'id="{element_id}"' in html, element_id
