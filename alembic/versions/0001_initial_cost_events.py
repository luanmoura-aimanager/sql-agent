"""initial schema: cost_events

Revision ID: 0001_initial_cost_events
Revises:
Create Date: 2026-05-30 (Sessão D-2 do trilho de cost attribution)

----------------------------------------------------------------------
Esta migration é o equivalente do que `alembic revision --autogenerate
-m "initial schema: cost_events"` produziria contra um DB vazio com o
`metadata` de `db.py` como `target_metadata`.

Por que escrita à mão e não autogenerate?
  A primeira migration foi gerada na sessão D-2 sem Postgres ao alcance
  do autogenerate (rodado em sandbox sem Docker). Escrever à mão produz
  o mesmo resultado e força revisar cada coluna/constraint. Você pode
  validar pareando: `rm` esta migration → `docker compose up -d` →
  `alembic revision --autogenerate -m "initial schema: cost_events"` →
  comparar com este arquivo. O diff deve ser nulo (modulo ordem).

Por que ID `0001_initial_cost_events` em vez de hash random?
  Default do Alembic é hash de 12 hex chars. Funciona mas é hostil pra
  navegação visual em diretório com muitas migrations. Prefixo numérico
  + slug humano (`0001_initial_cost_events`, `0002_add_latency_ms`,
  etc.) é convenção comum em times que rodam dezenas de migrations.
  Alembic aceita qualquer string única como revision id.

O que esta migration cria:
  - Tabela cost_events com 9 colunas (ver db.py pra justificativa).
  - 3 CHECK constraints (input_tokens, output_tokens, cost_usd >= 0).
  - 2 índices (token_hash+occurred_at DESC, request_id).
  - Constraint names seguem naming_convention de db.py (ck_*, ix_*, pk_*).

Downgrade reverte tudo. Em billing real, downgrade de migration que
afeta cost_events é caso especial — você quase nunca quer perder dados
históricos. Pra esta migration inicial não tem dado a perder, então
DROP TABLE direto é seguro.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial_cost_events"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria cost_events com colunas, CHECKs e índices."""
    op.create_table(
        "cost_events",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("pricing_version", sa.Text(), nullable=False),
        # Nomes CURTOS de propósito: target_metadata (db.metadata) carrega a
        # naming_convention "ck_%(table_name)s_%(constraint_name)s", e o
        # op.create_table a aplica — gerando ck_cost_events_<nome> uma vez.
        # Repetir o prefixo aqui dobraria pra ck_cost_events_ck_cost_events_*.
        sa.CheckConstraint(
            "input_tokens >= 0",
            name="input_tokens_non_negative",
        ),
        sa.CheckConstraint(
            "output_tokens >= 0",
            name="output_tokens_non_negative",
        ),
        sa.CheckConstraint(
            "cost_usd >= 0",
            name="cost_usd_non_negative",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cost_events"),
    )
    # Índice composto (token_hash, occurred_at DESC) — cobre a query
    # principal "quanto X gastou desde Y?" com leitura do mais recente
    # pra trás SEM reverse scan.
    op.create_index(
        "ix_cost_events_token_hash_occurred_at",
        "cost_events",
        ["token_hash", sa.text("occurred_at DESC")],
        unique=False,
    )
    # Lookup pontual por request_id (correlaciona com X-Request-ID do log).
    op.create_index(
        "ix_cost_events_request_id",
        "cost_events",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove índices e tabela. Apaga dado histórico — usar com cuidado."""
    op.drop_index("ix_cost_events_request_id", table_name="cost_events")
    op.drop_index(
        "ix_cost_events_token_hash_occurred_at", table_name="cost_events"
    )
    op.drop_table("cost_events")
