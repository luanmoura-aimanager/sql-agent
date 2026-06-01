# Multi-stage build pro app FastAPI (Sessão Deployment do Cap 3).
#
# Stage 1 (builder): instala deps em venv.
# Stage 2 (runtime): só copia venv + código. Imagem final ~150-200MB.
#
# Por que multi-stage e não single?
#   - Dev deps (pytest, testcontainers, etc.) não vão pra prod — ficam só
#     no builder. Imagem runtime menor, superfície de ataque menor.
#   - Cache de deps separado do código: mudar main.py não invalida o
#     layer de pip install (que demora 30-60s).
#
# Por que python:3.11-slim e não alpine?
#   - Alpine usa musl libc; alguns wheels (asyncpg, psycopg) não têm
#     wheels musl pré-compilados → tem que compilar com gcc → build 5x
#     mais lento e imagem maior por causa do toolchain.
#   - slim é Debian minimal — ~120MB base, wheels glibc funcionam direto.
#
# Por que non-root user?
#   - Se app for comprometido, atacante não tem root no container. Defesa
#     em profundidade básica. Railway/Fly/etc rodam container com user
#     setado pela imagem — não force root.

# =========================================
# Stage 1: builder
# =========================================
FROM python:3.11-slim AS builder

# Variáveis úteis pro pip não criar arquivos ou perguntar coisas.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Cria venv isolada — copiada pro runtime no stage 2.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copia só requirements primeiro pra otimizar layer cache.
# Mudança em main.py não invalida esse layer; mudança em requirements.txt sim.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# =========================================
# Stage 2: runtime
# =========================================
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Cria user não-root antes de qualquer COPY pra ownership ficar certa.
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

# Copia venv do builder. Tudo o que app precisa em runtime mora aqui.
COPY --from=builder /opt/venv /opt/venv

# Copia código da app. .dockerignore filtra o que não precisa
# (.git, tests, py311env, etc.) pra não inflar imagem nem vazar segredo.
COPY --chown=app:app . .

USER app

# Railway injeta $PORT — bind em 0.0.0.0 pra aceitar tráfego externo
# (default 127.0.0.1 só aceitaria localhost dentro do container).
#
# --workers 1: Railway escala horizontalmente (mais réplicas) em vez de
# verticalmente (mais workers por réplica). 1 worker mantém pool de DB
# pequeno (5 conexões por réplica × N réplicas — fácil prever cota
# Postgres) e elimina shared state quirks entre workers no mesmo processo.
#
# CMD em shell form → Docker roda como `/bin/sh -c "..."`, então o `exec`
# substitui o shell pelo uvicorn (vira PID 1). Sem ele o shell fica de pai
# e engole o SIGTERM no shutdown, derrubando o graceful drain do uvicorn.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
