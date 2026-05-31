"""
Cost attribution — testes ponta a ponta da Sessão D-3.

Cobertura:
  Pricing (unitário, sem DB):
    - calculate_cost_usd faz contas com Decimal exato.
    - Modelo desconhecido raise KeyError.
    - Versão é exposta.

  Callback (unitário, sem app/DB):
    - Sem accumulator no scope, callback é no-op (não crasha).
    - Com accumulator, acumula tokens de múltiplos on_llm_end.
    - Captura model_name do primeiro on_llm_end.

  Integração (com testcontainers + TestClient mockado):
    - /query roda → INSERT em cost_events com totais corretos.
    - Log query_handled tem input_tokens/output_tokens/cost_usd.
    - call_count > 0 só insere quando o agente realmente chamou LLM.

Mock do agente: substituímos run_agent por uma função que simula o
callback (chama on_llm_end com dados conhecidos via cost_handler).
Isso evita gastar chamadas reais ao Anthropic em CI.
"""
import os
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select

os.environ.setdefault("API_TOKEN", "test-token")

import pricing  # noqa: E402
import db  # noqa: E402
from cost_callback import (  # noqa: E402
    CostCallbackHandler,
    cost_handler,
    init_accumulator,
    read_accumulator,
    reset_accumulator,
)


# ---------- Pricing (puro, sem DB) ----------


def test_pricing_version_loaded():
    assert pricing.get_version() == "2026-05-31"


def test_calculate_cost_usd_decimal_exact():
    """1000 input + 500 output @ $0.80/MTok in + $4.00/MTok out = $0.0028."""
    cost = pricing.calculate_cost_usd(
        "claude-haiku-4-5-20251001", 1000, 500
    )
    assert cost == Decimal("0.00280000")


def test_calculate_cost_usd_zero_tokens():
    """Zero tokens em ambos lados → cost zero. Sem crash."""
    cost = pricing.calculate_cost_usd("claude-haiku-4-5-20251001", 0, 0)
    assert cost == Decimal("0.00000000")


def test_calculate_cost_usd_unknown_model_raises():
    """Modelo fora da tabela → KeyError com mensagem útil."""
    with pytest.raises(KeyError) as excinfo:
        pricing.calculate_cost_usd("claude-future-99", 100, 100)
    assert "pricing.json" in str(excinfo.value)


def test_calculate_cost_usd_quantized_to_8_decimals():
    """Quantize garante que não passamos precisão maior que NUMERIC(12, 8)."""
    cost = pricing.calculate_cost_usd("claude-haiku-4-5-20251001", 7, 3)
    # 7/1M * 0.80 + 3/1M * 4.00 = 5.6e-6 + 1.2e-5 = 1.76e-5 = 0.00001760
    assert cost == Decimal("0.00001760")
    # Tem exatamente 8 casas decimais
    assert -cost.as_tuple().exponent == 8


# ---------- Callback (puro, sem app/DB) ----------


def _fake_llm_result(input_tokens: int, output_tokens: int, model: str):
    """Constrói LLMResult fake mimickando o que langchain-anthropic devolve.

    A estrutura mínima que o callback inspeciona é:
      response.generations[0][0].message.usage_metadata + .response_metadata
    Não importamos LLMResult de verdade pra manter o teste leve.
    """
    msg = SimpleNamespace(
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
        response_metadata={"model_name": model},
    )
    gen = SimpleNamespace(message=msg)
    return SimpleNamespace(generations=[[gen]], llm_output={})


def test_callback_no_op_outside_request_scope():
    """Sem init_accumulator antes, callback não crasha (eval CLI, startup)."""
    handler = CostCallbackHandler()
    handler.on_llm_end(_fake_llm_result(100, 50, "haiku"))
    # Como não tinha scope, nada pra inspecionar — só não pode crashar.
    assert read_accumulator() is None


def test_callback_accumulates_across_multiple_calls():
    """2 on_llm_end somam corretamente; model_name vem do primeiro."""
    handler = CostCallbackHandler()
    token = init_accumulator(token_hash="abc123")
    try:
        handler.on_llm_end(_fake_llm_result(100, 30, "claude-haiku-4-5-20251001"))
        handler.on_llm_end(_fake_llm_result(200, 50, "claude-haiku-4-5-20251001"))
        acc = read_accumulator()
        assert acc is not None
        assert acc["input_tokens"] == 300
        assert acc["output_tokens"] == 80
        assert acc["call_count"] == 2
        assert acc["model_name"] == "claude-haiku-4-5-20251001"
        assert acc["token_hash"] == "abc123"
    finally:
        reset_accumulator(token)


def test_callback_handles_missing_usage_gracefully():
    """Se usage_metadata vier vazio, callback não soma nada e não crasha."""
    handler = CostCallbackHandler()
    token = init_accumulator(token_hash="xyz")
    try:
        empty = SimpleNamespace(
            generations=[[SimpleNamespace(message=SimpleNamespace(
                usage_metadata={}, response_metadata={}
            ))]],
            llm_output={},
        )
        handler.on_llm_end(empty)
        acc = read_accumulator()
        assert acc is not None
        assert acc["input_tokens"] == 0
        assert acc["output_tokens"] == 0
        assert acc["call_count"] == 1
    finally:
        reset_accumulator(token)


def test_reset_accumulator_restores_default():
    """Sem reset, ContextVar vaza pra fora do scope (D-1 lesson)."""
    handler = CostCallbackHandler()
    token = init_accumulator(token_hash="t1")
    handler.on_llm_end(_fake_llm_result(50, 50, "claude-haiku-4-5-20251001"))
    assert read_accumulator() is not None
    reset_accumulator(token)
    assert read_accumulator() is None


# ---------- Integração: callback + pricing + INSERT no DB ----------


@pytest.fixture
def fake_run_agent(monkeypatch):
    """Substitui run_agent por uma versão que simula o callback.

    O run_agent real faz graph.invoke com Anthropic — caro e flaky em CI.
    Simulação: chama cost_handler.on_llm_end com tokens conhecidos
    (mimicando 2 calls = router + sql_agent) e devolve resposta canned.

    Pode ser parametrizado via attrs pra simular cenários (sem calls,
    1 call, modelo diferente, etc.).
    """
    def _factory(input_tokens=1000, output_tokens=500, model="claude-haiku-4-5-20251001", calls=2):
        def fake(question, history):
            handler = cost_handler
            for _ in range(calls):
                handler.on_llm_end(
                    _fake_llm_result(input_tokens // calls, output_tokens // calls, model)
                )
            return "answer"
        # Pacth no módulo main, que é onde /query importa.
        monkeypatch.setattr("main.run_agent", fake)
    return _factory


@pytest_asyncio.fixture
async def client(pg_engine, monkeypatch):
    """httpx.AsyncClient com main.app, depois de garantir que db.engine usa
    o Postgres efêmero da fixture (DATABASE_URL já foi setada por
    _migrated_database_url).

    Por que AsyncClient + ASGITransport e NÃO o TestClient do Starlette?
      TestClient roda o app ASGI num event loop SEPARADO (anyio blocking
      portal, thread de fundo). Já os fixtures pg_engine (TRUNCATE) e a
      leitura pós-request rodam no loop da sessão do pytest-asyncio.
      Conexões asyncpg ficam presas ao loop que as criou; quando o handler
      faz `async with db.engine.begin()` no loop do portal reusando uma
      conexão do pool presa ao loop da sessão, asyncpg explode com
      "another operation is in progress". AsyncClient roda o app NO MESMO
      loop do teste — handler-INSERT, TRUNCATE e leitura compartilham o
      loop e o asyncpg fica feliz. (Em prod, sob uvicorn de loop único, o
      `db.engine.begin()` do handler está correto — o mismatch só existe
      no harness de duas-loops do TestClient.)

    Note: import de main aqui pra rodar DEPOIS de DATABASE_URL ser
    configurada. Patch no db._engine pra reusar o engine da fixture
    em vez de criar outro pool no mesmo container.
    """
    monkeypatch.setattr(db, "_engine", pg_engine)
    from httpx import ASGITransport, AsyncClient
    from main import app, limiter, token_limiter
    limiter._storage.reset()
    token_limiter._storage.reset()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c


_TOKEN = os.environ["API_TOKEN"]
_AUTH_OK = {"Authorization": f"Bearer {_TOKEN}"}


async def test_query_inserts_cost_event(client, fake_run_agent, pg_engine):
    """Happy path: /query roda → INSERT em cost_events com totais corretos."""
    fake_run_agent(input_tokens=1000, output_tokens=500)
    r = await client.post(
        "/query",
        json={"question": "qual é a receita?", "history": []},
        headers=_AUTH_OK,
    )
    assert r.status_code == 200

    # Lê cost_events e confere a linha
    async with pg_engine.connect() as conn:
        rows = (await conn.execute(select(db.cost_events))).all()
    assert len(rows) == 1
    row = rows[0]._mapping
    assert row["input_tokens"] == 1000
    assert row["output_tokens"] == 500
    assert row["model_name"] == "claude-haiku-4-5-20251001"
    # 1000/1M * 0.80 + 500/1M * 4.00 = 0.0028
    assert row["cost_usd"] == Decimal("0.00280000")
    assert row["pricing_version"] == "2026-05-31"
    # request_id no DB bate com o header da response
    assert str(row["request_id"]) == r.headers["X-Request-ID"]


async def test_query_no_insert_when_no_llm_calls(client, monkeypatch, pg_engine):
    """Se o agente não chama nenhum LLM (degenerado), NÃO grava linha.

    Sem isso, gravaríamos linhas com cost=0 e model_name=NULL — poluindo
    a tabela com eventos não-billables.
    """
    def fake(question, history):
        # Sem chamar handler.on_llm_end → acc vazio → call_count=0.
        return "answer"
    monkeypatch.setattr("main.run_agent", fake)

    r = await client.post("/query", json={"question": "q", "history": []}, headers=_AUTH_OK)
    assert r.status_code == 200

    async with pg_engine.connect() as conn:
        rows = (await conn.execute(select(db.cost_events))).all()
    assert len(rows) == 0


async def test_query_handled_log_includes_cost_fields(client, fake_run_agent, caplog):
    """Log query_handled em INFO ganhou input_tokens, output_tokens, cost_usd."""
    import logging as _logging
    fake_run_agent(input_tokens=2000, output_tokens=1000)
    with caplog.at_level(_logging.INFO, logger="sql_agent.api"):
        r = await client.post("/query", json={"question": "q", "history": []}, headers=_AUTH_OK)
    assert r.status_code == 200

    handled = [r for r in caplog.records if r.message == "query_handled"]
    assert len(handled) == 1
    rec = handled[0]
    assert rec.input_tokens == 2000
    assert rec.output_tokens == 1000
    # 2000/1M * 0.80 + 1000/1M * 4.00 = 0.0016 + 0.004 = 0.0056
    assert rec.cost_usd == "0.00560000"
    assert rec.model_name == "claude-haiku-4-5-20251001"
    assert rec.pricing_version == "2026-05-31"
    assert rec.llm_call_count == 2


async def test_query_accumulator_isolation_between_requests(client, fake_run_agent, pg_engine):
    """Dois requests sequenciais NÃO somam tokens entre si (ContextVar isolation)."""
    fake_run_agent(input_tokens=1000, output_tokens=500)
    r1 = await client.post("/query", json={"question": "q1", "history": []}, headers=_AUTH_OK)
    r2 = await client.post("/query", json={"question": "q2", "history": []}, headers=_AUTH_OK)
    assert r1.status_code == 200 and r2.status_code == 200

    async with pg_engine.connect() as conn:
        rows = (await conn.execute(select(db.cost_events).order_by(db.cost_events.c.id))).all()
    assert len(rows) == 2
    # Cada linha tem os totais isolados (não acumulado entre requests)
    assert rows[0]._mapping["input_tokens"] == 1000
    assert rows[1]._mapping["input_tokens"] == 1000
