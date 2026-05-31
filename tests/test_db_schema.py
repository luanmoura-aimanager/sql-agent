"""
Testes do schema de `cost_events` contra Postgres real.

Setup: tests/conftest.py sobe um Postgres efêmero via testcontainers
e aplica `alembic upgrade head` antes do primeiro teste — testes não
validam só o `Table()` em Python; validam o pipeline migration→DB→app.

O que cobrimos (5 testes):
  1. INSERT válido passa e devolve dados consistentes.
  2. CHECK barra input_tokens negativo (invariante de banco).
  3. CHECK barra cost_usd negativo (invariante de banco).
  4. server_default NOW() preenche occurred_at quando omitido no INSERT.
  5. Índices e constraints existem com nomes da naming_convention.

O que NÃO está aqui (escopo):
  - Comportamento da app sobre o DB (vem em D-3 com o callback).
  - Lifecycle de connection pool (mockado em testes do app).
  - Performance / explain de queries (estaria em testes dedicados).
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

import db


_VALID_ROW = {
    "request_id": uuid.uuid4(),
    "token_hash": "abcdef012345",
    "model_name": "claude-haiku-4-5-20251001",
    "input_tokens": 1500,
    "output_tokens": 320,
    "cost_usd": Decimal("0.00412800"),
    "pricing_version": "2026-05-29",
}


async def test_insert_valid_row_roundtrip(pg_engine):
    """INSERT válido passa, SELECT devolve os mesmos dados, tipos preservados."""
    row = {**_VALID_ROW, "request_id": uuid.uuid4()}
    async with pg_engine.begin() as conn:
        result = await conn.execute(
            db.cost_events.insert().returning(db.cost_events.c.id),
            row,
        )
        inserted_id = result.scalar_one()

    async with pg_engine.connect() as conn:
        fetched = (
            await conn.execute(
                select(db.cost_events).where(db.cost_events.c.id == inserted_id)
            )
        ).one()

    m = fetched._mapping
    assert m["request_id"] == row["request_id"]
    assert m["token_hash"] == row["token_hash"]
    assert m["model_name"] == row["model_name"]
    assert m["input_tokens"] == row["input_tokens"]
    assert m["output_tokens"] == row["output_tokens"]
    # NUMERIC volta como Decimal — exatamente igual ao que entrou (sem
    # erro de float).
    assert m["cost_usd"] == row["cost_usd"]
    assert m["pricing_version"] == row["pricing_version"]
    # occurred_at preenchido pelo server_default
    assert m["occurred_at"] is not None
    # PK ordenável por inserção
    assert m["id"] == inserted_id


async def test_check_barrers_negative_input_tokens(pg_engine):
    """CHECK `ck_cost_events_input_tokens_non_negative` impede valor negativo.

    Invariante de banco — defesa em profundidade. Mesmo se o callback do
    langchain mandar -1 por bug, o INSERT falha em vez de gravar lixo.
    """
    row = {**_VALID_ROW, "request_id": uuid.uuid4(), "input_tokens": -1}
    with pytest.raises(IntegrityError) as excinfo:
        async with pg_engine.begin() as conn:
            await conn.execute(db.cost_events.insert(), row)
    # CheckViolation é o tipo de psycopg pra CHECK falhado
    assert "input_tokens_non_negative" in str(excinfo.value)


async def test_check_barrers_negative_cost_usd(pg_engine):
    """CHECK `ck_cost_events_cost_usd_non_negative` impede valor negativo.

    Caso mais crítico — billing com valor negativo é fraude potencial
    (crédito sem origem). DB barra antes mesmo de chegar no log.
    """
    row = {**_VALID_ROW, "request_id": uuid.uuid4(), "cost_usd": Decimal("-0.01")}
    with pytest.raises(IntegrityError) as excinfo:
        async with pg_engine.begin() as conn:
            await conn.execute(db.cost_events.insert(), row)
    assert "cost_usd_non_negative" in str(excinfo.value)


async def test_occurred_at_defaults_to_now_when_omitted(pg_engine):
    """`server_default=func.now()` preenche occurred_at se INSERT omitir.

    Importante porque o callback do langchain (D-3) vai inserir sem
    passar occurred_at — confia no DB pra timestampar com clock dele
    (não do app, que pode estar deslocado).
    """
    row = {**_VALID_ROW, "request_id": uuid.uuid4()}
    row.pop("occurred_at", None)  # garante que não está passando
    async with pg_engine.begin() as conn:
        result = await conn.execute(
            db.cost_events.insert().returning(db.cost_events.c.occurred_at),
            row,
        )
        ts = result.scalar_one()
    assert ts is not None
    # TIMESTAMPTZ — confere que tem tzinfo, não é naive
    assert ts.tzinfo is not None


async def test_naming_convention_applied(pg_engine):
    """Constraints e índices existem com nomes derivados da naming_convention.

    Sem naming_convention estável, autogenerate ficaria criando diffs
    falsos só de renomeação a cada release do SQLAlchemy. Esse teste
    pinns os nomes esperados — se algum dia mudarem, ou a convenção
    quebrar, falha aqui em vez de surpreender em prod.
    """
    expected_indexes = {
        "ix_cost_events_token_hash_occurred_at",
        "ix_cost_events_request_id",
    }
    expected_check_constraints = {
        "ck_cost_events_input_tokens_non_negative",
        "ck_cost_events_output_tokens_non_negative",
        "ck_cost_events_cost_usd_non_negative",
    }
    expected_pk = "pk_cost_events"

    async with pg_engine.connect() as conn:
        # Inspector é sync no SA — usar run_sync.
        def _gather(sync_conn):
            insp = inspect(sync_conn)
            return {
                "indexes": {i["name"] for i in insp.get_indexes("cost_events")},
                "checks": {
                    c["name"] for c in insp.get_check_constraints("cost_events")
                },
                "pk": insp.get_pk_constraint("cost_events")["name"],
            }

        info = await conn.run_sync(_gather)

    assert expected_indexes.issubset(info["indexes"]), (
        f"índices faltando: {expected_indexes - info['indexes']}"
    )
    assert expected_check_constraints.issubset(info["checks"]), (
        f"checks faltando: {expected_check_constraints - info['checks']}"
    )
    assert info["pk"] == expected_pk
