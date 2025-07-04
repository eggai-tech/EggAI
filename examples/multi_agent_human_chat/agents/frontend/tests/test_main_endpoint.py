"""Tests for the HTTP root endpoint (serving index.html)."""

import pytest
from fastapi.testclient import TestClient

from ..main import api, settings


@pytest.fixture(autouse=True)
def temp_public_dir(tmp_path, monkeypatch):
    """Monkey-patch settings.public_dir to a temporary directory."""
    monkeypatch.setattr(settings, "public_dir", str(tmp_path))
    return tmp_path


def test_read_root_success(temp_public_dir):
    """When index.html exists, GET / returns its contents."""
    html_file = temp_public_dir / "index.html"
    content = "<html><body>OK</body></html>"
    html_file.write_text(content, encoding="utf-8")
    client = TestClient(api)
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == content


def test_read_root_not_found(temp_public_dir):
    """When index.html is missing, GET / returns 404."""
    client = TestClient(api)
    response = client.get("/")
    assert response.status_code == 404


def test_read_root_error(temp_public_dir, monkeypatch):
    """When reading index.html raises an error, GET / returns 500."""
    html_file = temp_public_dir / "index.html"
    html_file.write_text("data", encoding="utf-8")
    # Simulate open() throwing an unexpected error
    import importlib
    main_mod = importlib.import_module("agents.frontend.main")
    monkeypatch.setattr(
        main_mod,
        'open',
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("fail")),
    )
    client = TestClient(api)
    response = client.get("/")
    assert response.status_code == 500
    assert "An error occurred" in response.json().get("detail", "")