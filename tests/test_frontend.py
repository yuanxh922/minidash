import pytest
from app.routes.frontend_routes import get_frontend_html, STATIC_INDEX_PATH


def test_ui_endpoint_returns_html(client):
    """GET /ui returns 200 OK with valid text/html content."""
    res = client.get("/ui")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    content = res.text
    assert "<!DOCTYPE html>" in content
    assert "MiniDash" in content
    assert "Choose a Restaurant" in content
    assert "Your Cart" in content
    assert "Order Lookup" in content
    assert "Status Audit History" in content


def test_dashboard_alias_returns_html(client):
    """GET /dashboard serves as an alias to the frontend single page app."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "<!DOCTYPE html>" in res.text


def test_root_content_negotiation_browser_html(client):
    """GET / returns HTML when Accept header includes text/html."""
    res = client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "<!DOCTYPE html>" in res.text


def test_root_content_negotiation_api_json(client):
    """GET / returns JSON health check when Accept header does not request HTML."""
    # Without Accept header
    res_default = client.get("/")
    assert res_default.status_code == 200
    assert res_default.json() == {"app": "MiniDash", "status": "ok"}

    # With JSON Accept header
    res_json = client.get("/", headers={"Accept": "application/json"})
    assert res_json.status_code == 200
    assert res_json.json() == {"app": "MiniDash", "status": "ok"}


def test_explicit_health_check_endpoint(client):
    """GET /health returns JSON status ok."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"app": "MiniDash", "status": "ok"}


def test_static_index_path_exists():
    """Verify static index.html file exists and has non-trivial size."""
    assert STATIC_INDEX_PATH.is_file()
    assert STATIC_INDEX_PATH.stat().st_size > 1000
