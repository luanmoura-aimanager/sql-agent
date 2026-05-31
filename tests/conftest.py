"""
Test fixtures pra testes que precisam de Postgres real.

Padrão (Sessão D-2 de cost attribution, 30/05/2026):

  1. Fixture session-scoped sobe UM container Postgres efêmero (mesma
     imagem do docker-compose.yml: `postgres:16-alpine`) pra toda a
     sessão de pytest. Custo: ~5-10s de startup uma vez, ~0s pros
     testes seguintes.

  2. Aplica `alembic upgrade head` no setup — o schema vem das mesmas
     migrations versionadas que rodariam em prod. Testes não estão
     validando só o `Table()` em Python; estão validando o pipeline
     migration → DB real.

  3. Cada teste recebe `pg_engine` (function-scoped) que **trunca a
     tabela `cost_events`** no setup pra isolar dados entre testes
     SEM precisar dropar/recriar o DB (que seria 10x mais lento).

  4. Tear-down derruba o container ao fim da sessão.

Pré-requisito: Docker daemon rodando (Colima, Docker Desktop, etc.).
Se Docker não estiver disponível, pytest pula esses testes com
mensagem clara em vez de falhar misteriosamente.
"""
import asyncio
import os
import subprocess

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Ryuk (reaper de cleanup do testcontainers) faz bind-mount do socket do
# Docker num container privilegiado. Em runtimes que montam o socket via
# virtiofs (Colima, alguns rootless), esse mount falha com "operation not
# supported" e NENHUM container de teste sobe. Desabilitar o Ryuk evita
# isso; o cleanup passa a depender do context manager `with
# PostgresContainer(...)` (que já temos no pg_container) — suficiente pra
# runs normais e pra CI efêmera. setdefault preserva override explícito.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# testcontainers tem fila de dependências que pode falhar import sem
# Docker rodando. Lazy import dentro da fixture, e detectamos a ausência
# pra dar mensagem útil.


def _docker_available() -> bool:
    """Checa se há um Docker daemon acessível. Sem daemon, testes que
    precisam de Postgres real são pulados em vez de explodirem."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="session")
def docker_or_skip():
    """Pula testes que dependem de Docker se não houver daemon disponível.

    Mensagem clara em vez do erro críptico de testcontainers quando
    Docker socket não existe.
    """
    if not _docker_available():
        pytest.skip(
            "Docker daemon não disponível — testes de Postgres pulados. "
            "Inicia com `colima start` ou abre Docker Desktop.",
            allow_module_level=True,
        )


@pytest.fixture(scope="session")
def pg_container(docker_or_skip):
    """Sobe um Postgres efêmero pra toda a sessão de pytest.

    Mesma imagem do docker-compose.yml — `postgres:16-alpine`. testcontainers
    cuida do startup wait (espera pg_isready) e tear-down.
    """
    from testcontainers.postgres import PostgresContainer

    # driver="asyncpg" explícito: get_connection_url() devolve direto a URL
    # com o driver async do app (postgresql+asyncpg://). Sem isso, dependia
    # do default do testcontainers (hoje psycopg2) + um .replace() frágil que
    # virava no-op se uma versão futura mudasse o default → engine async
    # recebendo driver sync. Pinar aqui é a fonte única do scheme.
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as pg:
        yield pg


@pytest.fixture(scope="session")
def _migrated_database_url(pg_container):
    """Aplica alembic upgrade head e devolve a connection string.

    Setamos DATABASE_URL no env porque alembic/env.py lê de lá (mesmo
    pattern do app — single source of truth pra conexão).
    """
    # URL já vem com asyncpg (driver pinado no pg_container); Alembic troca
    # pra psycopg internamente (ver alembic/env.py).
    url = pg_container.get_connection_url()
    os.environ["DATABASE_URL"] = url

    # Roda Alembic in-process via API (em vez de subprocess) pra honrar
    # o env atual da fixture e evitar overhead de spawn.
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield url


@pytest_asyncio.fixture(scope="session")
async def pg_engine_session(_migrated_database_url) -> AsyncEngine:
    """AsyncEngine reaproveitado entre testes. pool pequeno (não precisa
    do production tuning aqui)."""
    engine = create_async_engine(_migrated_database_url, pool_size=2)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_engine(pg_engine_session) -> AsyncEngine:
    """Engine por teste — trunca cost_events no setup pra isolar dados.

    TRUNCATE é 10x mais rápido que DROP+CREATE da tabela; permite testes
    rápidos em sequência mantendo isolamento.
    """
    from sqlalchemy import text

    async with pg_engine_session.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE cost_events RESTART IDENTITY"))
    yield pg_engine_session
    # Tear-down: deixa o cleanup pro próximo teste (mais barato em
    # média do que truncar duas vezes).


# pytest-asyncio mode: nossa preferência é `auto` — async functions
# viram async tests sem precisar de @pytest.mark.asyncio em cada um.
# Configuração via setup.cfg/pytest.ini também funcionaria, mas
# centralizar aqui mantém junto da fixture.
def pytest_collection_modifyitems(config, items):
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
