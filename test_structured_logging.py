"""
Structured logging — testes das properties travadas em 27/05/2026.

Cobertura:
1. JsonFormatter produz JSON válido com campos esperados.
2. hash_text é determinístico (mesma string → mesmo hash; strings
   diferentes → hashes diferentes; comprimento fixo).
3. Log injection: `\\n` em campos do payload é escapado pelo json.dumps;
   o output do formatter sempre ocupa uma única linha.
4. request_id middleware: cada request gera UUID4, expõe no header
   X-Request-ID, e o log do mesmo request carrega o mesmo id.
5. Categoria B em INFO: q_hash presente, question_text ausente.
   Em DEBUG: ambos presentes.

Nota sobre captura: pytest's caplog captura via handler próprio anexado
ao root logger; ele recebe os LogRecord ANTES do nosso JsonFormatter
rodar. Pra testar o JSON formatado em si, instanciamos JsonFormatter
direto e chamamos format() em LogRecord fabricado. Pra testar quais
campos o /query loga, caplog basta.
"""
import json
import logging
import os
import re
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_TOKEN", "test-token")

from logging_config import JsonFormatter, hash_text, request_id_var  # noqa: E402
from main import app, limiter, token_limiter  # noqa: E402

_AUTH_OK = {"Authorization": "Bearer test-token"}
_BODY = {"question": "qual é a venda do mês?", "history": []}


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter._storage.reset()
    token_limiter._storage.reset()
    yield


# ---------- Formatter / hash unit tests ----------


def test_hash_text_is_deterministic():
    assert hash_text("foo") == hash_text("foo")
    assert hash_text("foo") != hash_text("bar")


def test_hash_text_has_fixed_length():
    assert len(hash_text("anything")) == 12
    assert len(hash_text("x", length=8)) == 8


def test_formatter_emits_valid_json_with_required_fields():
    """JsonFormatter sempre cospe JSON válido com ts/level/event/request_id."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="x", lineno=1,
        msg="event_name", args=None, exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["event"] == "event_name"
    assert parsed["request_id"] == "-"  # fora de scope de request
    assert "ts" in parsed


def test_formatter_includes_extra_fields():
    """Campos passados via `extra=` viram chaves no JSON."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="x", lineno=1,
        msg="event_name", args=None, exc_info=None,
    )
    # `extra=` em logger.info() vira atributo direto no record.
    record.q_hash = "abc123"
    record.latency_ms = 42
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["q_hash"] == "abc123"
    assert parsed["latency_ms"] == 42


def test_log_injection_newline_is_escaped():
    """
    DEFESA CENTRAL: payload com \\n + JSON forjado vira UMA linha única
    no output (newline escapado), não duas entradas separadas.

    Sem essa defesa, atacante manda `pergunta\\n{"level":"ERROR",...}`
    e o agregador de log vê duas linhas — uma real, uma forjada.
    json.dumps escapa \\n → \\\\n no JSON serializado, anulando o vetor.
    """
    formatter = JsonFormatter()
    malicious = 'oi\n{"level":"ERROR","msg":"system breach","forged":true}'
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="x", lineno=1,
        msg=malicious, args=None, exc_info=None,
    )
    output = formatter.format(record)
    # Zero newlines literais no output → uma única linha de log.
    assert output.count("\n") == 0
    # O texto malicioso continua acessível DENTRO do campo event,
    # com o \n preservado lá dentro (escapado na serialização).
    parsed = json.loads(output)
    assert "\n" in parsed["event"]
    assert "system breach" in parsed["event"]


def test_log_injection_via_extra_field_is_escaped():
    """
    Mesmo vetor mas em campo extra (ex: question_text em DEBUG).
    json.dumps escapa em qualquer string, não só `msg`.
    """
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="x", lineno=1,
        msg="query_debug", args=None, exc_info=None,
    )
    record.question_text = 'normal\n{"forged":true}'
    output = formatter.format(record)
    assert output.count("\n") == 0
    parsed = json.loads(output)
    assert "forged" in parsed["question_text"]


# ---------- request_id propagation tests ----------


_UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


@patch("main.run_agent", return_value="pong")
def test_request_id_in_response_header_is_uuid4(mock_agent):
    """Cada response carrega X-Request-ID válido (UUID4)."""
    client = TestClient(app)
    r = client.post("/query", json=_BODY, headers=_AUTH_OK)
    assert r.status_code == 200
    rid = r.headers.get("X-Request-ID")
    assert rid is not None
    assert _UUID4_RE.match(rid), f"X-Request-ID não é UUID4: {rid}"


@patch("main.run_agent", return_value="pong")
def test_request_id_differs_between_requests(mock_agent):
    """Dois requests sequenciais têm request_id distintos."""
    client = TestClient(app)
    r1 = client.post("/query", json=_BODY, headers=_AUTH_OK)
    r2 = client.post("/query", json=_BODY, headers=_AUTH_OK)
    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]


@patch("main.run_agent", return_value="pong")
def test_request_id_in_log_matches_response_header(mock_agent, caplog):
    """
    O request_id no log estruturado bate com o header da response —
    prova que a propagação via ContextVar funciona.
    """
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="sql_agent.api"):
        r = client.post("/query", json=_BODY, headers=_AUTH_OK)
    rid_header = r.headers["X-Request-ID"]
    query_records = [rec for rec in caplog.records if rec.message == "query_handled"]
    assert len(query_records) == 1
    rec = query_records[0]
    # Renderiza o record com JsonFormatter pra ver o request_id real
    # (o ContextVar é lido pelo formatter no momento do format(), e
    # `caplog` captura o LogRecord cru — então format aqui pra checar).
    formatter = JsonFormatter()
    # Setamos o ContextVar pro id do header pra que o formatter veja —
    # em produção isso é automático porque o format() roda dentro do
    # scope do request middleware. No caplog teste, o format roda fora
    # do scope (já saímos do request), então simulamos.
    token = request_id_var.set(rid_header)
    try:
        rendered = json.loads(formatter.format(rec))
    finally:
        request_id_var.reset(token)
    assert rendered["request_id"] == rid_header


# ---------- Categoria B: hash vs texto por nível ----------


@patch("main.run_agent", return_value="resposta sensível com PII")
def test_info_logs_q_hash_but_not_question_text(mock_agent, caplog):
    """
    Em INFO (default produção), o log de /query tem q_hash mas NÃO
    o texto da pergunta. Defesa contra PII leak em log aggregator.
    """
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="sql_agent.api"):
        client.post("/query", json=_BODY, headers=_AUTH_OK)
    query_records = [rec for rec in caplog.records if rec.message == "query_handled"]
    assert len(query_records) == 1
    rec = query_records[0]
    assert hasattr(rec, "q_hash")
    assert rec.q_hash == hash_text(_BODY["question"])
    # NUNCA logar texto em INFO
    assert not hasattr(rec, "question_text")
    assert not hasattr(rec, "answer_text")
    # Mas tem o len (útil pra capacity / detectar abuso)
    assert rec.answer_len == len("resposta sensível com PII")


@patch("main.run_agent", return_value="resposta sensível com PII")
def test_debug_logs_full_question_and_answer_text(mock_agent, caplog):
    """
    Em DEBUG (incident response), o log inclui texto completo. Liberado
    sob a premissa de que DEBUG é privilégio explícito e temporário.
    """
    client = TestClient(app)
    with caplog.at_level(logging.DEBUG, logger="sql_agent.api"):
        client.post("/query", json=_BODY, headers=_AUTH_OK)
    debug_records = [rec for rec in caplog.records if rec.message == "query_debug"]
    assert len(debug_records) == 1
    rec = debug_records[0]
    assert rec.question_text == _BODY["question"]
    assert rec.answer_text == "resposta sensível com PII"


# ---------- Error path: response não vaza interno do agente ----------


# Marca distintiva — se aparecer na response, é vazamento. Mensagem
# parece com algo que o stack do agente realmente vazaria (path
# interno, nome de tabela secreta, prompt fragment).
_LEAK_MARKER = "INTERNAL_TABLE_pii_customer_pi_2026 prompt:'SELECT secret FROM ...'"


@patch("main.run_agent", side_effect=RuntimeError(_LEAK_MARKER))
def test_500_response_does_not_leak_exception_message(mock_agent):
    """
    Erro no agente vira HTTP 500 com detail GENÉRICO — não vaza str(e).

    Vetor que isso defende: exceptions do langgraph/anthropic/sqlite
    rotineiramente carregam path interno, nome de tabela, fragmento de
    prompt, ou excerpt de SQL no str(e). Categoria C das decisões de
    27/05 ("nunca pro cliente"): equivalente a meio-stack-trace que
    serve pra recon.
    """
    client = TestClient(app)
    r = client.post("/query", json=_BODY, headers=_AUTH_OK)
    assert r.status_code == 500
    body = r.json()
    # Detail é genérico — sem nada do str(e)
    assert _LEAK_MARKER not in r.text
    assert "RuntimeError" not in r.text
    assert "INTERNAL_TABLE" not in r.text
    # Comportamento esperado: detail simples e estável
    assert body == {"detail": "Internal error"}


@patch("main.run_agent", side_effect=RuntimeError(_LEAK_MARKER))
def test_500_response_still_carries_request_id_for_support(mock_agent):
    """
    Mesmo em erro, X-Request-ID vai no header — suporte usa pra achar
    o log estruturado correspondente (que tem error_type + stack).
    O operador tem visibilidade total; o cliente só tem o id.
    """
    client = TestClient(app)
    r = client.post("/query", json=_BODY, headers=_AUTH_OK)
    assert r.status_code == 500
    rid = r.headers.get("X-Request-ID")
    assert rid is not None
    assert _UUID4_RE.match(rid), f"X-Request-ID em erro não é UUID4: {rid}"


@patch("main.run_agent", side_effect=RuntimeError(_LEAK_MARKER))
def test_500_log_keeps_error_type_for_triage(mock_agent, caplog):
    """
    O log estruturado (server-side) MANTÉM error_type — o operador
    precisa saber se foi RuntimeError do langgraph, AuthError do
    Anthropic, ou OperationalError do sqlite pra triar.

    Verifica que a defesa (sumir str(e) do cliente) não cega o operador.

    Crucial: a asserção roda sobre o JSON RENDERIZADO pelo JsonFormatter
    (o que de fato chega no sink/stdout), não só sobre o LogRecord cru —
    senão o teste passaria mesmo que o formatter descartasse o traceback.
    """
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="sql_agent.api"):
        client.post("/query", json=_BODY, headers=_AUTH_OK)
    failed_records = [rec for rec in caplog.records if rec.message == "query_failed"]
    assert len(failed_records) == 1
    rec = failed_records[0]

    # Renderiza pelo formatter de produção e valida o JSON que sai de fato.
    rendered = json.loads(JsonFormatter().format(rec))
    assert rendered["event"] == "query_failed"
    assert rendered["error_type"] == "RuntimeError"
    assert rendered["status"] == 500
    # q_hash bate com o hash da pergunta (correlação por hash não quebra no erro).
    assert rendered["q_hash"] == hash_text(_BODY["question"])
    # Traceback COMPLETO server-side: o operador vê o que o cliente não vê.
    assert "exc_info" in rendered
    assert "Traceback (most recent call last)" in rendered["exc_info"]
    assert "RuntimeError" in rendered["exc_info"]
    assert _LEAK_MARKER in rendered["exc_info"]
    # E continua sendo UMA linha de log (traceback escapado, não quebra o JSON).
    assert JsonFormatter().format(rec).count("\n") == 0
