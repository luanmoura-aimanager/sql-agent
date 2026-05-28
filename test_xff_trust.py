"""
Trust model do X-Forwarded-For no IP rate limit.

Cenários cobertos:
1. TRUSTED_PROXIES vazio (default) → XFF é IGNORADO; o peer IP é usado.
   Clientes diferentes mandando XFFs diferentes ainda compartilham quota.
2. TRUSTED_PROXIES inclui o peer → XFF é RESPEITADO; cada cliente
   simulado tem sua própria quota.

Por que monkeypatch em main.TRUSTED_PROXIES e não setar env var?
  A env var é lida no import do módulo. Pra um teste poder mudar o
  trust model sem reimportar, get_client_ip lê TRUSTED_PROXIES do
  globals() do módulo a cada chamada. Monkeypatch dessa variável é
  suficiente e mantém o teste self-contained.

Notas de TestClient:
  Por default, request.client.host é a string "testclient".
  Isso é o "peer" do ponto de vista do app — então pra simular
  "estou atrás de proxy", basta colocar "testclient" em TRUSTED_PROXIES.
"""
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ.setdefault("API_TOKEN", "test-token")

import main  # noqa: E402 — env var must be set first
from main import app, limiter, token_limiter  # noqa: E402

_AUTH_BAD = {"Authorization": "Bearer wrong-token"}
_BODY = {"question": "ping", "history": []}


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter._storage.reset()
    token_limiter._storage.reset()
    yield


@pytest.fixture
def _no_trusted_proxies(monkeypatch):
    """Default: sem proxies confiáveis. XFF deve ser ignorado."""
    monkeypatch.setattr(main, "TRUSTED_PROXIES", set())
    yield


@pytest.fixture
def _trust_testclient(monkeypatch):
    """Simula deploy atrás de proxy: peer 'testclient' é confiável."""
    monkeypatch.setattr(main, "TRUSTED_PROXIES", {"testclient"})
    yield


def test_xff_ignored_when_no_trusted_proxies(_no_trusted_proxies):
    """
    Sem TRUSTED_PROXIES setado, XFF não conta. Dois 'clientes' mandando
    XFFs distintos compartilham a quota (porque o peer 'testclient' é
    o mesmo). 61º request → 429.
    """
    client = TestClient(app)
    # 60 reqs alternando o XFF — todos devem cair no MESMO bucket
    # (o do peer 'testclient'), porque XFF não é confiável aqui.
    for i in range(60):
        xff = f"10.0.0.{i % 5}"
        r = client.post("/query", json=_BODY, headers={**_AUTH_BAD, "X-Forwarded-For": xff})
        assert r.status_code == 401, f"req {i + 1} got {r.status_code}"
    # 61º request — IP layer deve bater 429 (peer compartilhado)
    r = client.post(
        "/query",
        json=_BODY,
        headers={**_AUTH_BAD, "X-Forwarded-For": "10.0.0.99"},
    )
    assert r.status_code == 429


def test_xff_respected_when_peer_trusted(_trust_testclient):
    """
    Com TRUSTED_PROXIES incluindo o peer, XFF passa a definir o bucket.
    Cliente A esgota a quota; cliente B (XFF diferente) ainda consegue.
    """
    client = TestClient(app)
    headers_a = {**_AUTH_BAD, "X-Forwarded-For": "203.0.113.10"}
    headers_b = {**_AUTH_BAD, "X-Forwarded-For": "203.0.113.20"}

    # 60 reqs do cliente A — bucket dele lota
    for i in range(60):
        r = client.post("/query", json=_BODY, headers=headers_a)
        assert r.status_code == 401, f"warmup A req {i + 1} got {r.status_code}"

    # 61º do A: 429 (quota dele estourou)
    assert client.post("/query", json=_BODY, headers=headers_a).status_code == 429

    # Cliente B começa do zero — não compartilha bucket
    assert client.post("/query", json=_BODY, headers=headers_b).status_code == 401


def test_xff_leftmost_ip_is_used(_trust_testclient):
    """
    XFF padrão: 'client, proxy1, proxy2'. O cliente real é o leftmost.
    Dois requests com mesma cadeia (mesmo cliente real, proxies diferentes)
    devem cair no MESMO bucket.
    """
    client = TestClient(app)
    chain_1 = {**_AUTH_BAD, "X-Forwarded-For": "203.0.113.50, 10.0.0.1"}
    chain_2 = {**_AUTH_BAD, "X-Forwarded-For": "203.0.113.50, 10.0.0.2"}

    for i in range(60):
        headers = chain_1 if i % 2 == 0 else chain_2
        r = client.post("/query", json=_BODY, headers=headers)
        assert r.status_code == 401, f"req {i + 1} got {r.status_code}"

    # 61º request, qualquer chain do mesmo cliente real → 429
    assert client.post("/query", json=_BODY, headers=chain_1).status_code == 429


def test_xff_malformed_falls_back_to_peer(_trust_testclient):
    """
    Header vazio ou só com vírgulas/espaços → fallback ao peer IP.
    Não pode crashar nem virar burlador (string vazia como bucket key).
    """
    client = TestClient(app)
    bad_headers = {**_AUTH_BAD, "X-Forwarded-For": "   ,  , "}

    # 60 reqs com XFF malformado — todos vão pro bucket do peer 'testclient'
    for i in range(60):
        r = client.post("/query", json=_BODY, headers=bad_headers)
        assert r.status_code == 401, f"req {i + 1} got {r.status_code}"
    # 61º bate 429
    assert client.post("/query", json=_BODY, headers=bad_headers).status_code == 429
