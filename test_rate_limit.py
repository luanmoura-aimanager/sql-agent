import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ.setdefault("API_TOKEN", "test-token")

from main import app, limiter  # noqa: E402 — env var must be set first

_TOKEN = os.environ["API_TOKEN"]
_AUTH_OK = {"Authorization": f"Bearer {_TOKEN}"}
_AUTH_BAD = {"Authorization": "Bearer wrong-token"}
_BODY = {"question": "ping", "history": []}


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter._storage.reset()
    yield


@patch("main.run_agent", return_value="pong")
def test_60_valid_requests_all_200(mock_agent):
    client = TestClient(app)
    for i in range(60):
        r = client.post("/query", json=_BODY, headers=_AUTH_OK)
        assert r.status_code == 200, f"request {i + 1} got {r.status_code}"


@patch("main.run_agent", return_value="pong")
def test_61st_valid_request_is_429(mock_agent):
    client = TestClient(app)
    for _ in range(60):
        client.post("/query", json=_BODY, headers=_AUTH_OK)
    r = client.post("/query", json=_BODY, headers=_AUTH_OK)
    assert r.status_code == 429
    assert "retry-after" in r.headers


def test_60_invalid_token_requests_all_401():
    client = TestClient(app)
    for i in range(60):
        r = client.post("/query", json=_BODY, headers=_AUTH_BAD)
        assert r.status_code == 401, f"request {i + 1} got {r.status_code}"


def test_61st_invalid_token_is_429():
    """Rate limit applies before auth — 429 even with wrong token."""
    client = TestClient(app)
    for _ in range(60):
        client.post("/query", json=_BODY, headers=_AUTH_BAD)
    r = client.post("/query", json=_BODY, headers=_AUTH_BAD)
    assert r.status_code == 429
