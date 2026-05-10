# ADR-003: Router scope — what counts as "in-scope" for sql_agent

**Status:** Accepted
**Date:** 2026-05-08
**Context PR:** #16

## Context

The agent uses a 2-node graph: a `router` classifies user messages as YES
(send to `sql_agent`) or NO (send to `direct`). The original router prompt
defined the YES condition as *"questions that can be answered by querying
this database"* and listed expected terms (customers, products, orders,
sales, cities, prices, quantities).

The Week 6 evaluation harness (eval.py + 30-case calibration set) revealed
three classes of misrouting:

1. **Destructive commands** (DROP, DELETE, TRUNCATE, UPDATE) routed to
   `direct`, which then refused politely *and* showed the SQL command as
   an "example" — exposing an attack surface the system was supposed to
   block.
2. **Database questions with absurd premises** (e.g., "customers on Mars",
   "orders from 1850") routed to `direct`, which responded "I don't have
   access" instead of the correct behavior of querying the DB and reporting
   0 rows.
3. **Schema lookups** (e.g., "data type of the price column") inconsistently
   routed depending on phrasing.

Root cause: the prompt asked the router to anticipate *fulfillment*
("can be answered by SELECT?") rather than *scope* ("is this about the
database system?"). That misframing pushed the router into the sql_agent's
job of deciding what to do with the request.

## Decision

Reframe the router's task from "can the SELECT answer this?" to
**"is this message in scope of the database system, regardless of whether
the system can fulfill it?"**

Specific changes to the router prompt:

- Replace the enumerated term list with three positive criteria covering
  the system's full surface: queries, commands, and metadata.
- Explicitly include edge-case examples ("on Mars", "in 1850",
  "credit score") so the model fixes the pattern by example, not by
  abstract instruction.
- Mention the downstream sql_agent and its SELECT-only guard, signaling
  that delegation is safe even for destructive commands — the guard
  acts as the layer of defense the router doesn't need to enforce.

The router is now agnostic to whether the system *can* fulfill the
request; it only routes by topic.

## Consequences

### Positive
- Main eval suite: **5/8 → 8/8**. Destructive commands now reach
  `sql_agent`, which refuses naturally because its only tools are
  `get_schema` and `run_query` (read-only). Absurd-premise questions
  (Mars, 1850, nonexistent fields) now get queried and return 0/empty.
- The agent stops the "I don't have access" framing for in-scope
  requests, which was both technically false and a UX problem.
- Defense-in-depth becomes more legible: layer 1 is the *interface
  surface* of `sql_agent` (only read-only tools exposed); layer 2 is
  the MCP server's SELECT-only guard. Both still active.

### Negative
- Router prompt grew from ~9 lines to ~25 lines. Input-token cost
  per request is marginally higher (~150 extra tokens at most), and
  router calls are 1 per turn.
- The positive criteria list is a manual artifact: if the system
  gains a new category (e.g., write capabilities, RAG over docs), the
  router prompt has to be updated explicitly.

### Trade-off considered and rejected
- *Alternative:* drop the router entirely and always send to `sql_agent`.
  Rejected because off-topic messages ("what is SQL?", "how does an LLM
  work?") would burn tool calls and produce worse responses than `direct`
  for general-knowledge questions. The router earns its complexity in
  the off-topic case.

## Validation

Calibration before/after the router change (30 cases):

| Metric | Before | After |
|---|---|---|
| Judge pass rate | 20/30 | 25/30 |
| Human pass rate (refreshed) | 23/30 | 28/30 |
| Cohen's κ | 0.831 | 0.526¹ |
| Disagreements | 2 | 3² |

¹ Kappa drop is the kappa paradox (high pass rate + skewed class
distribution increases expected agreement, depressing κ even when
observed agreement is high). Not a regression.
² Three remaining disagreements are pre-existing — two human-drift cases
on ambiguity criterion, one criterion non-observability bug — and are
unrelated to this change.
