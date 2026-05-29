"""
Database layer — Postgres async via SQLAlchemy 2.0 Core + asyncpg.

Por que esse módulo existe (sessão 29/05/2026 — Sessão D-1):
  Cost attribution precisa de auditabilidade real (categoria C do
  opener de telemetria: billing-grade, reconstrução de cálculo,
  retenção). Stdout log não basta — log aggregator perde retenção
  após N dias, não tem schema rígido, e billing real exige UPSERT
  / idempotência / queries por intervalo.

  Postgres é o destino certo. Esse módulo define:
    1. O schema da tabela `cost_events` (fact table, append-only).
    2. O engine async com pool configurado.
    3. Helper temporário pra criar a tabela (será removido em D-2
       quando Alembic entrar).

Decisões travadas (ver project_sql_agent_2026_05_29 na memória):
  - Driver: asyncpg via SQLAlchemy 2.0 async Core (não ORM).
    Razão: cost_events é fact table append-only sem relacionamentos.
    Core dá tipagem + Alembic + pool sem overhead de mapping.
  - Pool: size=5, overflow=10, timeout=30s, recycle=1h, pre_ping=True.
    Razão: volume baixo (5 é generoso); defesas anti-zumbi (recycle)
    e anti-flake (pre_ping) são gratuitas e evitam classes de bug.
  - Schema: BIGSERIAL PK + UUID request_id + TIMESTAMPTZ + NUMERIC(12,8).
    Razão: dinheiro nunca em float (NUMERIC), tempo sempre com tz
    (TIMESTAMPTZ), PK ordenado por inserção (BIGSERIAL).
"""
import os

from dotenv import load_dotenv
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    Uuid,
    func,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Carrega .env se existir. Faz o `cp .env.example .env` do README funcionar
# de fato — sem isso, db.py lê os.environ direto e o passo do smoke quebra
# com KeyError mesmo seguindo a doc à risca. load_dotenv não sobrescreve
# vars já setadas no shell (precedência: shell > .env), então é seguro.
load_dotenv()


# Naming convention pra constraints. Sem isso, Alembic gera nomes
# automáticos que mudam entre versões do SQLAlchemy — migration files
# acabam com diffs falsos só de renomeação. Convenção explícita
# estabiliza nomes; Alembic gera diffs reais e nada além.
#
# Padrão recomendado pela SQLAlchemy + Alembic docs.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ----------------------------------------------------------------------
# Schema: cost_events
# ----------------------------------------------------------------------
#
# Fact table append-only. Cada linha = um evento de chamada de LLM com
# custo associado. Ver decisão 1 da Sessão D-1 pra justificativa de
# cada coluna; resumo:
#
#   id              — surrogate PK ordenável por tempo de inserção.
#                     BIGSERIAL (não UUID) porque PK em event store
#                     se beneficia de ordem natural; UUID v4 é random
#                     e prejudica B-tree.
#
#   request_id      — UUID que bate com X-Request-ID do log estruturado.
#                     Permite join "log -> evento de cost" via id externo,
#                     sem precisar de FK (tabelas independentes).
#
#   occurred_at     — TIMESTAMPTZ (com timezone). Postgres guarda em UTC,
#                     converte na leitura conforme session timezone.
#                     Defesa contra a categoria clássica de bug
#                     "servidor UTC, app BRT, log local, billing UTC".
#                     server_default NOW() pra simplificar INSERT.
#
#   token_hash      — fingerprint do Bearer token (hash_text do
#                     logging_config). Agrega cost por cliente sem
#                     guardar o token em texto.
#
#   model_name      — string completa "claude-haiku-4-5-20251001".
#                     Importante registrar versão exata: o mesmo
#                     "haiku" pode ter pricing diferente em snapshots.
#
#   input_tokens,
#   output_tokens   — INTEGER, CHECK >= 0. Custo = sum(tokens * price).
#                     CHECK como invariante explícita; pegamos bug se
#                     callback do langchain um dia mandar -1 por erro.
#
#   cost_usd        — NUMERIC(12, 8) com CHECK >= 0.
#                     12 dígitos / 8 decimais = até $9999.99999999.
#                     NUMERIC, NUNCA FLOAT, em dinheiro: float acumula
#                     erro (0.1 + 0.2 != 0.3) e bugs de billing são
#                     dos mais caros. Decimal exato.
#
#   pricing_version — string identificando qual versão do pricing.json
#                     foi usada no cálculo. Auditabilidade: quando
#                     preço muda em julho e em outubro alguém pergunta
#                     "por que esse evento custou X?", a resposta precisa
#                     estar gravada na linha. Sem isso, reconstrução
#                     do cálculo é impossível.
#
# Índices:
#   ix_cost_events_token_hash_occurred_at — cobre a query principal
#     ("quanto X gastou desde Y?"). DESC pra ts permite range scans
#     eficientes do mais recente pra trás.
#   ix_cost_events_request_id — lookup pontual ("o que esse request
#     custou?"). Cardinalidade alta, busca exata.
#
# O que NÃO está aqui (deliberado): q_hash, sql_hash, latency_ms,
# status. Esses ficam SÓ no log estruturado. cost_events tem escopo
# de billing; quem precisa de join faz join (request_id é a chave).
# Princípio: tabela faz uma coisa bem.
cost_events = Table(
    "cost_events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("request_id", Uuid, nullable=False),
    Column(
        "occurred_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("token_hash", Text, nullable=False),
    Column("model_name", Text, nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cost_usd", Numeric(12, 8), nullable=False),
    Column("pricing_version", Text, nullable=False),
    # CHECKs como invariantes de banco. Cliente errado pode mandar
    # qualquer coisa via app — o DB barra antes da linha ser gravada.
    # Defesa em profundidade: app valida, DB confirma.
    CheckConstraint("input_tokens >= 0", name="input_tokens_non_negative"),
    CheckConstraint("output_tokens >= 0", name="output_tokens_non_negative"),
    CheckConstraint("cost_usd >= 0", name="cost_usd_non_negative"),
)

# Índices definidos fora da Table pra poder referenciar a coluna como
# expressão (occurred_at.desc()) — a forma string-only de dentro da Table
# não permite especificar direção. btree é o default do Postgres, então
# não precisa de postgresql_using explícito.
Index(
    "ix_cost_events_token_hash_occurred_at",
    cost_events.c.token_hash,
    # DESC de verdade: a query principal ("quanto X gastou desde Y?") lê
    # do mais recente pra trás. Índice descendente serve esse ORDER BY
    # sem reverse scan.
    cost_events.c.occurred_at.desc(),
)
Index("ix_cost_events_request_id", cost_events.c.request_id)


# ----------------------------------------------------------------------
# Engine
# ----------------------------------------------------------------------
#
# Singleton lazy. Criado na PRIMEIRA vez que `engine` é usado, não no
# import. Pool gerencia as conexões internas.
#
# Por que lazy e não no import? Ler DATABASE_URL no nível do módulo faz
# qualquer `import db` crashar com KeyError quando a var não está setada
# — inclusive coleta de pytest se um módulo testado (futuro main.py em
# D-3) importar db transitivamente. Adiar a leitura pro primeiro uso
# preserva o fail-fast onde importa (servidor que tenta usar o DB sem
# config morre na hora) sem transformar o import num campo minado.
#
# Por que ler DATABASE_URL via os.environ direto e não via Pydantic
# Settings ou similar? Mantemos a barra baixa: pattern de env var
# direto é o que já temos no resto do app (API_TOKEN, TRUSTED_PROXIES).
# Settings class virá quando crescer pra justificar.
#
# Por que fail-fast (KeyError) no primeiro uso se DATABASE_URL não setada?
# Servidor sem DB conectável é um zombie útil pra request, inútil pra
# billing. Melhor crashar do que processar request por horas e perder
# INSERT silenciosamente. Mesma filosofia do API_TOKEN.

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Engine singleton, criado sob demanda. Lê DATABASE_URL na primeira
    chamada (fail-fast com KeyError se ausente). Reusado nas seguintes."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            os.environ["DATABASE_URL"],
            pool_size=5,           # conexões permanentes idle prontas
            max_overflow=10,       # picos toleráveis antes de saturar Postgres
            pool_timeout=30,       # segundos de espera antes de raise
            pool_recycle=3600,     # recicla a cada 1h (anti-zumbi via NAT/firewall)
            pool_pre_ping=True,    # SELECT 1 antes de checkout (anti-flake)
            echo=False,            # True = SQL no log (útil em dev manual)
        )
    return _engine


def __getattr__(name: str):
    """PEP 562: `db.engine` resolve pro singleton lazy sem leitura no import.
    Mantém a ergonomia `db.engine` pra chamadores (smoke, futuros handlers)
    enquanto adia DATABASE_URL pro primeiro acesso de verdade."""
    if name == "engine":
        return get_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ----------------------------------------------------------------------
# init_db — temporário pra D-1
# ----------------------------------------------------------------------
#
# Cria a tabela direto a partir do metadata. Útil pro smoke test inicial
# antes do Alembic entrar (D-2). Quando Alembic estiver configurado,
# essa função vai sumir — schema vira responsabilidade exclusiva das
# migrations.
#
# Por que não deixar de uma vez? Sequência didática: ver SQLAlchemy
# criando tabela sozinha esclarece o que ele faz com o Table object,
# antes de adicionar a camada de Alembic em cima.
async def init_db() -> None:
    """Cria todas as tabelas do metadata. NÃO usar em prod — só dev/smoke."""
    async with get_engine().begin() as conn:
        await conn.run_sync(metadata.create_all)


async def drop_db() -> None:
    """Drop todas as tabelas. Apenas pra cleanup de smoke/testes."""
    async with get_engine().begin() as conn:
        await conn.run_sync(metadata.drop_all)
