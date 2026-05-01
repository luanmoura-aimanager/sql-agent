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

The graph has **three nodes** and one conditional branch. The SQL sub-agent no longer has direct database access — all DB operations go through the MCP server.

| Node | Purpose |
|---|---|
| `router` | Cheap single-turn LLM call that decides YES/NO: does this question need SQL? |
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
├── agent.py                      # LangGraph graph, nodes, tools, run_agent()
├── eval.py                       # Evaluation runner — calls run_agent() directly
├── eval_cases/
│   └── cases.yaml                # Test cases (question + regex assertions)
├── mcp/
│   └── sqlite-mcp-server.py      # Standalone MCP server (get_schema, run_query)
├── docs/
│   └── adr/
│       ├── 001-mcp-adoption.md   # Decision record: why MCP was adopted
│       └── 002-extract-agent-logic.md  # Decision record: agent/UI separation
├── create_db.py                  # One-time script to create and seed store.db
├── requirements.txt
└── store.db                      # SQLite database file (generated by create_db.py)
```

---

## Eval harness

`eval.py` runs a suite of regression tests against the live agent without starting Streamlit:

```bash
python eval.py
```

Test cases live in `eval_cases/cases.yaml`. Each case has a question and a regex-based assertion (`regex`, `regex_all`, `regex_any`, or `regex_none`). Categories cover aggregation, metadata queries, router decisions, adversarial inputs, and missing-data edge cases.

---

## Run locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Recreate the database — store.db is already committed
python create_db.py

# 3. Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Launch the app
streamlit run app.py
```

The MCP server is spawned automatically by `app.py` — no separate process to start.

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
