# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (Python 3.11, use py311env or a fresh venv)
pip install -r requirements.txt

# Set required environment variable
export ANTHROPIC_API_KEY="sk-ant-..."

# Run the Streamlit app
streamlit run app.py

# Run the FastAPI server (requires fastapi and uvicorn)
uvicorn main:app --reload

# Run regex + LLM-judge eval suite
python eval.py

# Generate agent answers for the 30-case calibration set
python gen_outputs.py        # writes eval_cases/calibration_outputs.json

# Collect human pass/fail verdicts interactively
python human_judge.py        # writes eval_cases/human_judgments.json

# Run the LLM judge against calibration outputs
python judge_outputs.py      # writes eval_cases/judge_judgments.json

# (Re)create the demo database — store.db is already committed
python create_db.py
```

The MCP server (`mcp/sqlite-mcp-server.py`) is spawned automatically as a subprocess by `agent.py` — no separate process to start.

## Architecture

The core flow is a **LangGraph `StateGraph`** with three nodes and one conditional branch:

```
User question → router (LLM) → YES → sql_agent (ReAct loop) → END
                              → NO  → direct (plain LLM call) → END
```

- **[agent.py](agent.py)** — contains everything: `State`, the three node functions (`router`, `sql_agent`, `direct`), the graph definition, and `run_agent(question, chat_history)`, the single public entry point.
- **[app.py](app.py)** — thin Streamlit wrapper; holds `chat_history` in `session_state` and calls `run_agent()` on each turn.
- **[mcp/sqlite-mcp-server.py](mcp/sqlite-mcp-server.py)** — standalone MCP server (FastMCP, stdio transport). Exposes two tools: `get_schema` (returns table/column names) and `run_query` (SELECT-only guard, 100-row cap). Requires `SQL_AGENT_DB_PATH` env var. The SELECT-only guard is string-prefix based and is the intended enforcement layer — not the agent.

### Router design

The router classifies by **scope** (is this about the database system?), not by anticipated fulfillment. Destructive commands (`DROP`, `DELETE`, etc.) and absurd-premise questions are routed `YES` to `sql_agent`, which handles them safely via the read-only MCP interface. See [docs/adr/003-router-scope.md](docs/adr/003-router-scope.md).

### Conversation memory

Memory is managed by the caller. `run_agent()` accepts `chat_history` as a list of `{"role": ..., "content": ...}` dicts, converts them to LangGraph messages, and appends the new question before invoking the graph. The agent itself is stateless.

### Model

All nodes use `claude-haiku-4-5-20251001` via `langchain_anthropic.ChatAnthropic`. The LLM-as-judge in `eval.py` uses `claude-sonnet-4-5` directly via the `anthropic` SDK.

## Eval harness

Three tiers in [eval_cases/](eval_cases/):

1. **Regex regression** (`eval.py` + `eval_cases/cases.yaml`) — fast, no API cost. Methods: `regex`, `regex_all`, `regex_any`, `regex_none`.
2. **LLM-as-judge** — also in `eval.py`; cases use `method: llm_judge` with a `criteria` field. Uses assistant-turn prefill (`{"role": "assistant", "content": "{"}`) to force JSON output.
3. **Human-judgment calibration** — 30-case set in `eval_cases/calibration_set.yaml`. Current baseline: **28/30 (93.3%)** after router hardening.

## Key env vars

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (required) | Anthropic API access |
| `SQL_AGENT_DB_PATH` | `"store.db"` | Path to the SQLite database file |
