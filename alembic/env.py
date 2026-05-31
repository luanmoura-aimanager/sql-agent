"""
Alembic environment — customizado pra esse projeto.

Mudanças vs template padrão (`alembic init alembic`):

1. **`target_metadata` aponta pro nosso `db.metadata`** — Alembic enxerga
   nosso schema-em-Python e consegue fazer `alembic revision --autogenerate`
   detectando diferenças entre o `Table()` do `db.py` e o DB real.

2. **`sqlalchemy.url` vem de `DATABASE_URL` env var, não do alembic.ini** —
   12-factor (config no ambiente, não no código), mesma source que o app.
   Em dev casa com o docker-compose; em CI vem da fixture do testcontainers;
   em prod virá do secret manager.

3. **Driver sync pra Alembic** — asyncpg é async, e Alembic ainda assume
   driver sync no online mode (a versão async existe mas é mais código).
   Aqui trocamos `postgresql+asyncpg://` por `postgresql+psycopg://` só
   pra rodar as migrations; o app continua usando asyncpg em runtime.
   Pragmatismo: migration é one-shot, performance não importa, async
   adiciona complexidade desnecessária.

4. **`load_dotenv()`** — mesma razão do `db.py`: usuário seguindo o README
   (cp .env.example .env) precisa que o .env seja lido aqui também.
"""
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# Importa metadata do projeto. Por isso o env.py mora em alembic/ na raiz —
# precisa achar `db.py` no sys.path.
from db import metadata  # noqa: E402

load_dotenv()


# Alembic Config object (lê alembic.ini)
config = context.config

# Logging do alembic.ini (formato dos prints durante upgrade/downgrade)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# target_metadata = nosso schema. Sem isso, --autogenerate não consegue
# detectar diferenças (devolve "no changes detected" sempre).
target_metadata = metadata


# ------------------------------------------------------------------
# DATABASE_URL: lê do env, troca driver async → sync pra Alembic.
# ------------------------------------------------------------------
import os  # noqa: E402

raw_url = os.environ["DATABASE_URL"]
# asyncpg é async-only; Alembic online mode espera driver sync.
# psycopg (v3) é o sync de referência hoje. Troca só do prefixo do dialect
# preserva user/pass/host/db do mesmo Postgres.
sync_url = raw_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    """Modo offline: gera SQL em vez de aplicar no DB.

    Útil pra revisar diff antes de subir, ou pra fluxos de CI/CD que
    coletam SQL pra DBA aprovar. Não usamos no fluxo padrão, mas é
    grátis manter.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online: conecta no Postgres e aplica migration de verdade.

    NullPool: cada execução do alembic é um processo curto que abre e
    fecha conexão; pool com warm connections é desperdício e complica
    o shutdown.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # render_as_batch=False (default): emite ALTER TABLE direto.
            # Para SQLite seria True (não suporta ALTER COLUMN); pra
            # Postgres mantemos False, é mais rápido e gera SQL nativo.
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
