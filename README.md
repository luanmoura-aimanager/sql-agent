# SQL Agent

A Streamlit chat app that lets you query a SQLite database in natural language. You type a question, and a LangGraph-powered agent decides whether it needs to run SQL, executes the query safely via an MCP server, and returns a human-readable answer — all backed by Claude via the Anthropic API.

---

## Architecture overview

```
User question
      │
      ▼
┌─────────────┐    YES    ┌─────────────────────────────────────┐
│   router    │──────────▶│         sql_agent (ReAct)           │──┐
│  (LLM call) │           │  ↳ get_schema tool (MCP)            │  │
└─────────────┘           │  ↳ run_query tool  (MCP)            │  │
      │                   └─────────────────────────────────────┘  │
      │                                  │                          │
      │ NO               ┌───────────────┴──────────────────────┐  │
      └─────────────────▶│           direct (LLM call)          │  │
                         └──────────────────────────────────────┘  │
                                         │                          │
                                         ▼                          ▼
                                        END ◀───────────────────────┘

                                         ▲
                        ┌────────────────┴──────────────────────────┐
                        │        mcp/sqlite-mcp-server.py           │
                        │   get_schema ── run_query (SELECT-only)   │
                        │         transport: stdio                   │
                        └───────────────────────────────────────────┘
```

The graph has **three nodes** and one conditional branch. The SQL sub-agent no longer has direct database access — all DB operations go through the MCP server. The router classifies by *scope* (is this about the database system?) rather than by anticipated fulfillment, so destructive commands and absurd-premise questions are all forwarded to `sql_agent` — the SELECT-only guard in the MCP server is the enforcement layer.

> See [docs/adr/003-router-scope.md](docs/adr/003-router-scope.md) for the decision record behind the router redesign.

| Node | Purpose |
|---|---|
| `router` | Cheap single-turn LLM call that decides YES/NO: is this message in scope of the database system? |
| `sql_agent` | A full ReAct loop — the model thinks, calls `get_schema` and/or `run_query` via MCP, observes the result, and repeats until it can answer. |
| `direct` | A plain LLM call for questions that don't need data (greetings, explanations, follow-ups). |

---

## Key concepts explained

### LangGraph `StateGraph`

LangGraph lets you define agentic workflows as a directed graph. Each **node** is a Python function that receives the shared `State` dict and returns a partial update. **Edges** wire nodes together; **conditional edges** let you branch based on runtime values.

```python
builder = StateGraph(State)
builder.add_node("router", router)
builder.add_conditional_edges("router", route_decision, {"YES": "sql_agent", "NO": "direct"})
graph = builder.compile()
```

### State and message accumulation

The `State` TypedDict has a `messages` field annotated with `add`:

```python
class State(TypedDict):
    messages: Annotated[list, add]  # new messages are appended, not replaced
    needs_sql: str
```

This means every node can safely append messages without clobbering the history.

### ReAct agent (`create_react_agent`)

The SQL sub-agent uses the **ReAct** (Reason + Act) pattern:

1. **Think** — the model decides what to do next (check schema or write a query).
2. **Act** — it calls `get_schema` or `run_query` (both backed by the MCP server).
3. **Observe** — it reads the result.
4. **Repeat or answer** — if more data is needed it loops; otherwise it returns a natural-language answer.

`create_react_agent` builds this loop automatically from a model and a list of tools.

### MCP server (`mcp/sqlite-mcp-server.py`)

The database logic lives in a standalone **MCP (Model Context Protocol) server** instead of being hardcoded in `app.py`. The server exposes two tools over `stdio` transport:

| Tool | Description |
|---|---|
| `get_schema` | Returns all table names and their columns — the agent calls this first to discover the database structure dynamically. |
| `run_query` | Executes a `SELECT` query and returns up to 100 rows formatted as a readable string. |

`app.py` spawns the server as a subprocess for each tool call via `call_mcp_tool()`. This architecture means any other agent (Claude Desktop, another LangGraph app) can consume the same server without any code duplication.

> See [docs/adr/001-mcp-adoption.md](docs/adr/001-mcp-adoption.md) for the full decision record behind this design.

### `run_query` safety guard

Only `SELECT` queries are accepted. The guard lives in the MCP server — the correct trust boundary — rather than scattered across clients. Any query that does not start with `SELECT` is rejected before hitting the database. Results are truncated to 100 rows to keep LLM context manageable.

> **Known limitation:** the guard is a string-prefix heuristic and is vulnerable to stacked queries (`SELECT ...; DROP ...`). In production, prefer a read-only SQLite connection or a proper SQL parser (e.g. `sqlglot`).

### Dynamic schema discovery

Previously the database schema was hardcoded in the system prompt. Now the agent discovers it at runtime by calling `get_schema` — which means the system prompt stays schema-agnostic and the agent adapts automatically if the database changes.

### Conversation memory

Multi-turn memory is managed by the caller, not by LangGraph. `run_agent(question, chat_history)` accepts the full conversation history as a list of `{"role": ..., "content": ...}` dicts, converts them to LangGraph messages, and appends the new question before invoking the graph.

Streamlit's `session_state` holds `chat_history` and passes it on every call. This keeps the agent stateless — easier to test and evaluate in isolation (see `eval.py`).

> See [docs/adr/002-extract-agent-logic.md](docs/adr/002-extract-agent-logic.md) for the decision record behind this design.

---

## Database schema

A demo store database (`store.db`) with three tables:

| Table | Columns | Description |
|---|---|---|
| `customers` | id, name, city, email | People who place orders |
| `products` | id, name, category, price | Items available in the store |
| `orders` | id, customer_id, product_id, quantity, order_date | Purchase records linking customers to products |

The agent answers in English. Try:
- *"How many customers do we have?"*
- *"Which product generated the most revenue?"*
- *"How many orders were placed in March 2024?"*

---

## Project structure

```
sql-agent/
├── app.py                        # Streamlit UI — thin wrapper over run_agent()
├── main.py                       # FastAPI server — POST /query HTTP interface
├── agent.py                      # LangGraph graph, nodes, tools, run_agent()
├── eval.py                       # Regex + LLM-judge evaluation runner
├── gen_outputs.py                # Generate agent answers for calibration set
├── human_judge.py                # CLI to collect human pass/fail verdicts
├── eval_cases/
│   ├── cases.yaml                # Regex eval test cases
│   ├── calibration_set.yaml      # 30-case human-judgment calibration set
│   ├── calibration_outputs.json  # Agent answers for calibration cases
│   ├── human_judgments.json      # Human verdicts (pass/fail + reason)
│   ├── judge_judgments.json      # LLM-judge verdicts
│   └── notes.md                  # Baseline notes and failure analysis
├── mcp/
│   └── sqlite-mcp-server.py      # Standalone MCP server (get_schema, run_query)
├── docs/
│   └── adr/
│       ├── 001-mcp-adoption.md   # Decision record: why MCP was adopted
│       ├── 002-extract-agent-logic.md  # Decision record: agent/UI separation
│       └── 003-router-scope.md         # Decision record: router scope redesign
├── create_db.py                  # One-time script to create and seed store.db
├── requirements.txt
└── store.db                      # SQLite database file (generated by create_db.py)
```

---

## Eval harness

Three complementary methods, in increasing fidelity order:

### 1. Regex-based regression (`eval.py`)

Fast, deterministic, no API cost. Run with:

```bash
python eval.py
```

Test cases live in `eval_cases/cases.yaml`. Each case has a question and a regex assertion (`regex`, `regex_all`, `regex_any`, or `regex_none`). Categories cover aggregation, metadata queries, router decisions, adversarial inputs, and missing-data edge cases.

### 2. LLM-as-judge

`eval.py` also supports an LLM judge mode (see `--help`). The model grades each answer against a natural-language criterion instead of a regex.

### 3. Human-judgment calibration

The gold standard. A 30-case calibration set (`eval_cases/calibration_set.yaml`) covers the same categories as the regex suite but with richer, prose criteria.

**Workflow:**

```bash
# Step 1 — generate agent answers for all 30 cases
python gen_outputs.py          # writes eval_cases/calibration_outputs.json

# Step 2 — record human verdicts interactively
python human_judge.py          # writes eval_cases/human_judgments.json
```

`human_judge.py` is a terminal CLI: it shows question + criterion + agent answer for each case and asks for a `p`ass / `f`ail / `s`kip verdict with an optional reason. Progress is saved after every verdict so it can be interrupted and resumed.

**Baseline (2026-05-04): 23 / 30 (76.7%) → After router hardening (2026-05-08): 28 / 30 (93.3%)**

| Category | Baseline | After router hardening |
|---|---|---|
| Aggregation (simple, min/max, group-by) | 12 / 12 | 12 / 12 |
| Metadata | 2 / 3 | 3 / 3 |
| Adversarial (destructive) | 0 / 4 | 4 / 4 |
| Nonexistent data | 1 / 3 | 3 / 3 |
| Ambiguous | 3 / 3 | 3 / 3 |
| Not a DB question | 3 / 3 | 3 / 3 |
| Typos / casual | 2 / 2 | 2 / 2 |

The router was redesigned to classify by *scope* rather than anticipated fulfillment — destructive commands and absurd-premise questions are now routed to `sql_agent`, which handles them cleanly via its read-only tool interface. See [docs/adr/003-router-scope.md](docs/adr/003-router-scope.md).

---

## Run locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Recreate the database — store.db is already committed
python create_db.py

# 3. Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Launch the Streamlit app
streamlit run app.py

# 4b. Or run the FastAPI server
uvicorn main:app --reload
```

The MCP server is spawned automatically — no separate process to start.

## Cost events DB (local dev)

A second database — Postgres — holds **cost events**: append-only audit log of LLM calls (tokens in/out, USD cost, model, request_id). This is separate from `store.db` (the agent's read-only data source) and from the structured stdout logs (telemetry). Postgres is the persistence layer for billing-grade auditability; stdout logs cover observability; SQLite serves agent queries.

```bash
# 1. Spin up Postgres locally (docker-compose.yml)
docker compose up -d

# 2. Copy env and adjust if needed (DATABASE_URL casa com docker-compose por default).
#    db.py carrega o .env automaticamente (python-dotenv) — não precisa exportar.
cp .env.example .env

# 3. (One-time) install the new deps
pip install -r requirements.txt

# 4. Smoke test — creates the cost_events table, inserts a row, reads it back
python scripts/smoke_cost_events.py
```

Schema lives in `db.py` as a SQLAlchemy 2.0 `Table` object. Schema changes are versioned via **Alembic** migrations in `alembic/versions/`:

```bash
# Apply all pending migrations (default in fresh dev setup)
alembic upgrade head

# Generate a new migration after editing the schema in db.py
alembic revision --autogenerate -m "add some_column"

# Inspect history / current state
alembic history
alembic current

# Roll back the most recent migration
alembic downgrade -1
```

`alembic/env.py` reads `DATABASE_URL` from the environment (same source as the app — single source of truth). For migrations, it transparently swaps the `asyncpg` driver for `psycopg` (sync), since Alembic doesn't need async; the app runtime keeps using `asyncpg`.

### Tests against real Postgres (testcontainers)

```bash
# Requires Docker daemon (Colima or Docker Desktop) running
pytest tests/
```

The test suite spins up an ephemeral `postgres:16-alpine` container per session (via `testcontainers`), runs `alembic upgrade head` automatically, and tears down at the end. Tests run against the same schema/Postgres version that will run in production — no SQLite-substitute mocking. Each test starts with a truncated table for isolation.

If Docker isn't available, the tests skip cleanly with a clear message (no cryptic error).

To stop Postgres: `docker compose down` (volume persists) or `docker compose down -v` (wipes data).

## REST API (`main.py`)

A FastAPI interface is available alongside the Streamlit UI, exposing the same agent logic over HTTP.

### Endpoints

#### `GET /health`

Returns `{"status": "ok"}`. Use this to check that the server is up before sending queries.

#### `POST /query`

Requires a Bearer token in the `Authorization` header. The server compares it against the `API_TOKEN` environment variable set at startup.

```json
// Request
{ "question": "Which product generated the most revenue?" }

// With conversation history (optional)
{
  "question": "And the least?",
  "history": [
    { "role": "user",      "content": "Which product generated the most revenue?" },
    { "role": "assistant", "content": "The top product is Widget A with $12,400." }
  ]
}

// Response
{ "answer": "..." }
```

**Auth status codes:**

| Scenario | Status |
|---|---|
| Valid Bearer token | `200` |
| Invalid token (`Bearer wrong`) | `401` — `{"detail": "Invalid token"}` |
| Non-Bearer scheme | `401` — `{"detail": "Invalid auth scheme"}` |
| Missing `Authorization` header | `422` (FastAPI schema validation) |
| Agent raised an exception | `500` — `{"detail": "Internal error"}` (genérico — a causa não vaza pro cliente; correlacione pelo header `X-Request-ID` no log estruturado) |

The 422 for missing header is a known wrinkle of using `Header(...)` — semantically it'd be cleaner as 401. Refactor candidate.

Start the server with both env vars set:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export API_TOKEN="<your-shared-secret>"
uvicorn main:app --reload
```

Example call:

```bash
curl -X POST localhost:8000/query \
  -H "Authorization: Bearer <your-shared-secret>" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many customers?"}'
```

Interactive docs are available at `http://localhost:8000/docs` once the server is running.

## Deploy on Railway (FastAPI + Postgres)

The FastAPI app + Postgres are designed to deploy together on Railway. Config-as-code in `railway.toml`; CI gate via GitHub Actions before auto-deploy.

```bash
# 1. (One-time) install Railway CLI: brew install railway
railway login
railway init           # links repo to a new Railway project
railway add --plugin postgresql   # provisions managed Postgres
```

Then in the Railway dashboard, set the app service env vars:

```
ANTHROPIC_API_KEY = sk-ant-...
API_TOKEN         = <fresh prod token>     # gerar com: python -c "import secrets; print(secrets.token_urlsafe(32))"
TRUSTED_PROXIES   = <Railway edge IP>      # depois de identificar via inspect — XFF trust precisa pra IP rate limit funcionar atrás do proxy deles
```

`DATABASE_URL` is auto-injected by Railway when the Postgres service is linked — don't set it manually.

```bash
# 2. First deploy
git push origin main   # triggers Railway auto-deploy via GitHub integration

# Railway applies pre-deploy:
#   alembic upgrade head     (declared in railway.toml [deploy].preDeployCommand)
# Then starts the container:
#   uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1
```

CI (`.github/workflows/ci.yml`) runs `pytest` on every PR and push to `main`. Railway only deploys after CI is green — `main` vermelho não chega em produção.

Healthcheck: Railway pings `/health` (exempt do rate limit) e só promove a réplica quando 200.

Workers: 1 por container — Railway escala horizontalmente (mais réplicas). Mantém pool de DB pequeno (5 conexões × N réplicas, fácil prever).

## Deploy on Streamlit Cloud

1. Fork or push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo.
3. Set the main file to `app.py`.
4. Add your Anthropic API key in **Settings → Secrets**:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

`SQL_AGENT_DB_PATH` is optional — it defaults to `"store.db"` in the working directory, which is where Streamlit Cloud places the repo root. Set it explicitly only if you want to point at a different database file.

The `mcp/` directory must be committed to the repo so the server script is available at runtime.

## Roadmap / Side-missions

Items that are not blocking current work but **must be resolved before a production deploy**.

| Priority | Item | Context |
|----------|------|---------|
| 🔴 Before deploy | **X-Forwarded-For / reverse proxy** | `get_remote_address` reads `request.client.host` (proxy IP, not client IP). All clients share the same rate-limit quota behind nginx/ALB/Cloudflare. Fix: `get_ipaddr` helper + uvicorn `--forwarded-allow-ips` or `ProxyHeadersMiddleware`. Forging `X-Forwarded-For` is a known vuln — only trust the header from known proxy IPs. See `main.py` `TODO(deploy)` comment. |
| 🟡 Multi-worker | **Redis backend for rate-limit storage** | In-memory storage resets on restart and is not shared across uvicorn workers. Needs `slowapi` Redis backend when going multi-instance. |
| 🟡 RFC 6750 | **WWW-Authenticate header on 401s** | 401 responses should include `WWW-Authenticate: Bearer realm="sql-agent"` per RFC 6750. Currently missing. Tracked from PR #22/#23 auth governance work. |
