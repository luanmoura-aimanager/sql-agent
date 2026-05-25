import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ.setdefault("API_TOKEN", "test-token")

from main import app, limiter, token_limiter, verify_token  # noqa: E402 — env var must be set first

_TOKEN = os.environ["API_TOKEN"]
_AUTH_OK = {"Authorization": f"Bearer {_TOKEN}"}
_AUTH_BAD = {"Authorization": "Bearer wrong-token"}
_BODY = {"question": "ping", "history": []}


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter._storage.reset()
    token_limiter._storage.reset()
    yield


@patch("main.run_agent", return_value="pong")
def test_30_valid_requests_under_token_limit(mock_agent):
    """Token layer: 30 requests com mesmo token válido ficam dentro da quota."""
    client = TestClient(app)
    for i in range(30):
        r = client.post("/query", json=_BODY, headers=_AUTH_OK)
        assert r.status_code == 200, f"request {i + 1} got {r.status_code}"


@patch("main.run_agent", return_value="pong")
def test_31st_valid_request_hits_token_limit(mock_agent):
    """Token layer: 31º request com mesmo token válido → 429 com Retry-After."""
    client = TestClient(app)
    for _ in range(30):
        client.post("/query", json=_BODY, headers=_AUTH_OK)
    r = client.post("/query", json=_BODY, headers=_AUTH_OK)
    assert r.status_code == 429
    assert "retry-after" in r.headers


@patch("main.run_agent", return_value="pong")
def test_two_tokens_have_separate_quotas(mock_agent):
    """Dois tokens diferentes têm contadores independentes — quota não é compartilhada."""
    app.dependency_overrides[verify_token] = lambda: None
    try:
        client = TestClient(app)
        headers_a = {"Authorization": "Bearer token-aaa"}
        headers_b = {"Authorization": "Bearer token-bbb"}
        for _ in range(30):
            client.post("/query", json=_BODY, headers=headers_a)
        assert client.post("/query", json=_BODY, headers=headers_a).status_code == 429
        assert client.post("/query", json=_BODY, headers=headers_b).status_code == 200
    finally:
        del app.dependency_overrides[verify_token]


@patch("main.run_agent", return_value="pong")
def test_ip_and_token_limits_coexist(mock_agent):
    """IP layer (60/min) e token layer (30/min) têm contadores separados.

    Fluxo: 30 reqs válidos esgotam o token counter. Mais 29 reqs inválidos
    incrementam apenas o IP counter (auth falha antes de chegar ao decorator).
    O 60º total dispara o IP limit — provando que os dois layers são independentes.
    """
    client = TestClient(app)

    # 30 reqs com token válido: IP=30, token=30, todos 200
    for i in range(30):
        r = client.post("/query", json=_BODY, headers=_AUTH_OK)
        assert r.status_code == 200, f"valid request {i + 1} got {r.status_code}"

    # 31º com token válido: token counter esgotado → 429 token limit; IP=31
    r = client.post("/query", json=_BODY, headers=_AUTH_OK)
    assert r.status_code == 429

    # 29 reqs com token inválido: apenas IP counter sobe (32→60); token counter intocado
    for i in range(29):
        r = client.post("/query", json=_BODY, headers=_AUTH_BAD)
        assert r.status_code == 401, f"invalid-token request {i + 1} got {r.status_code}"

    # 61º request total: IP counter = 61 → 429 do IP layer
    r = client.post("/query", json=_BODY, headers=_AUTH_BAD)
    assert r.status_code == 429


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


def test_health_exempt_from_rate_limit():
    """/health never 429s — @limiter.exempt keeps LB probes from tripping the limit."""
    client = TestClient(app)
    for i in range(100):
        r = client.get("/health")
        assert r.status_code == 200, f"request {i + 1} got {r.status_code}"
