"""
Smoke test contra Postgres real — útil pra inspeção manual em dev.

Pré-requisito:
    docker compose up -d
    cp .env.example .env
    pip install -r requirements.txt
    alembic upgrade head    # aplica schema (Sessão D-2 em diante)

Rodar:
    python scripts/smoke_cost_events.py

O que prova:
    - DATABASE_URL conecta no Postgres do docker-compose.
    - INSERT de um evento de exemplo passa pelos CHECKs.
    - SELECT devolve a linha de volta com todos os campos.
    - CHECK constraint barra cost_usd negativo (defesa em profundidade).

Diferença vs Sessão D-1: o smoke NÃO cria mais a tabela (eram init_db/
drop_db, removidos quando Alembic entrou). Schema é responsabilidade do
`alembic upgrade head`. Smoke só valida que o app consegue ler/escrever.

Pra suite de testes automatizada (CI, pré-PR), ver tests/test_db_schema.py
que sobe Postgres efêmero via testcontainers.
"""
import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

# Ajusta sys.path pra importar db.py da raiz do projeto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

import db  # noqa: E402


async def main() -> None:
    print(f"DATABASE_URL = {os.environ['DATABASE_URL']}")
    print()
    print("(Pré-requisito: alembic upgrade head)")
    print()

    print("1. Inserindo evento de exemplo…")
    rid = uuid.uuid4()
    async with db.engine.begin() as conn:
        result = await conn.execute(
            db.cost_events.insert().returning(db.cost_events.c.id),
            {
                "request_id": rid,
                "token_hash": "abc123def456",
                "model_name": "claude-haiku-4-5-20251001",
                "input_tokens": 1500,
                "output_tokens": 320,
                # Decimal explícito pra evitar conversão pra float
                "cost_usd": Decimal("0.00412800"),
                "pricing_version": "2026-05-29",
            },
        )
        inserted_id = result.scalar_one()
    print(f"   → inserted id={inserted_id}, request_id={rid}")

    print("2. Lendo a linha de volta via SELECT…")
    async with db.engine.connect() as conn:
        row = (
            await conn.execute(
                select(db.cost_events).where(db.cost_events.c.id == inserted_id)
            )
        ).one()
    print(f"   → {dict(row._mapping)}")

    print()
    print("3. Defesa: CHECK constraint barra cost_usd negativo")
    try:
        async with db.engine.begin() as conn:
            await conn.execute(
                db.cost_events.insert(),
                {
                    "request_id": uuid.uuid4(),
                    "token_hash": "x",
                    "model_name": "claude-haiku-4-5-20251001",
                    "input_tokens": 100,
                    "output_tokens": 100,
                    "cost_usd": Decimal("-1.00000000"),
                    "pricing_version": "2026-05-29",
                },
            )
        print("   ✗ CHECK não disparou — algo errado!")
        sys.exit(1)
    except IntegrityError as e:
        print(f"   ✓ DB barrou negativo: {type(e.orig).__name__}")

    print()
    print("✓ Smoke OK — engine, INSERT, SELECT e CHECK funcionam.")
    print("  (Linhas inseridas ficam no DB — use `alembic downgrade base &&")
    print("   alembic upgrade head` pra zerar, ou rode o teste contra um DB")
    print("   efêmero via testcontainers.)")
    await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
