"""
Smoke test pra db.py — Sessão D-1.

Pré-requisito:
    docker compose up -d
    cp .env.example .env
    pip install -r requirements.txt

Rodar:
    python scripts/smoke_cost_events.py

O que prova:
    - DATABASE_URL conecta no Postgres do docker-compose.
    - metadata.create_all cria a tabela cost_events com schema correto.
    - INSERT de um evento de exemplo passa pelos CHECKs.
    - SELECT devolve a linha de volta com todos os campos.
    - CHECK constraint barra cost_usd negativo (defesa em profundidade).
    - drop_db limpa pra próxima execução ficar idempotente.

Em D-2 isso vira fixture pytest com testcontainers; por ora, é um
arquivo standalone pra ver a coisa funcionando de ponta a ponta.
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

    print("1. Drop tabela se existe (limpeza idempotente)…")
    await db.drop_db()

    print("2. Criando schema via metadata.create_all…")
    await db.init_db()

    print("3. Inserindo evento de exemplo…")
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

    print("4. Lendo a linha de volta via SELECT…")
    async with db.engine.connect() as conn:
        row = (
            await conn.execute(
                select(db.cost_events).where(db.cost_events.c.id == inserted_id)
            )
        ).one()
    print(f"   → {dict(row._mapping)}")

    print()
    print("5. Defesa: CHECK constraint barra cost_usd negativo")
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
    print("6. Limpando (drop_db) pra próxima execução ser idempotente…")
    await db.drop_db()

    print()
    print("✓ Smoke OK — schema, engine, INSERT, SELECT e CHECK funcionam.")
    await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
