# ADR-002: Extract agent logic from app.py into agent.py

## Status
Accepted (2026-05-01)

## Context

All LangGraph graph logic (state definition, node functions, graph compilation), model instantiation, tool definitions, and MCP helpers lived directly in `app.py` alongside the Streamlit UI code. This made the agent logic untestable in isolation — any evaluation script had to either import the full Streamlit app or duplicate the agent implementation.

As the project added an eval harness (`eval.py` + `eval_cases/`), having a clean, importable agent boundary became necessary.

## Decision

Extract all non-UI code from `app.py` into a new `agent.py` module and expose a single public function:

```python
def run_agent(question: str, chat_history: list) -> str:
```

`app.py` becomes a thin Streamlit wrapper that imports `run_agent` and manages UI state. `eval.py` imports the same function directly without touching Streamlit.

As part of this change, `MemorySaver` (LangGraph's in-memory checkpointer) was removed. Instead, Streamlit's `session_state` holds the chat history and passes it as `chat_history` on each `run_agent` call. The agent reconstructs the message list from that dict list for each turn.

## Alternatives considered

- **Keep everything in `app.py` and duplicate logic in `eval.py`:** rejected — two copies of the agent diverge silently.
- **Keep `MemorySaver` and pass `thread_id` to `run_agent`:** rejected — adds an opaque dependency (the checkpointer object) to the public interface and complicates testing. Explicit `chat_history` is easier to reason about and mock.
- **Move to a class-based agent:** considered but unnecessary for this scope; a single function is sufficient.

## Consequences

**Positive:**
- `eval.py` can import and call `run_agent` without touching Streamlit or any UI state.
- Clear module boundary: `agent.py` owns agent behaviour, `app.py` owns presentation.
- `MemorySaver` is gone — no hidden state between calls; each `run_agent` invocation is self-contained given the `chat_history` input.

**Negative:**
- `MemorySaver`'s multi-turn persistence is now the caller's responsibility. If a future integration forgets to pass `chat_history`, the agent appears to have amnesia.
- `agent.py` is still a module-level singleton (graph compiled at import time); parallel test runs share the same compiled graph object.

## Related

- [ADR-001: Adopt MCP for SQL tool exposure](001-mcp-adoption.md)
