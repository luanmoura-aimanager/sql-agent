# Eval baseline notes

## Regex eval suite history

| Date | Score | Notes |
|---|---|---|
| 2026-05-01 | 7/8 | First run — `nonexistent_data` failing |
| 2026-05-09 | 5/8 | LLM-judge migration revealed 3 false positives masked by regex |
| 2026-05-10 | 8/8 | Router hardening (ADR-003) fixed all three failure classes |

## Human-judgment calibration history

| Date | Score | Notes |
|---|---|---|
| 2026-05-04 | 23/30 (76.7%) | Baseline — router using fulfillment framing |
| 2026-05-08 | 28/30 (93.3%) | After router scope reframe (ADR-003) |

---

## Resolved failures

### `nonexistent_data` — "customers on Mars"

**Was:** router misclassified absurd-premise questions as non-database, routing them to `direct`,
which replied "I don't have access." No query was ever run.

**Fixed by:** ADR-003 router reframe — scope-based routing now sends these to `sql_agent`, which
queries the DB and correctly returns 0 rows.

### `refuse_drop` / `refuse_delete` — adversarial SQL commands

**Was:** both cases passed, but for the wrong reason — the router sent them to `direct`, which
refused politely. The MCP SELECT-only guard was never exercised.

**Fixed by:** ADR-003 — destructive commands are now explicitly in-scope for `sql_agent`. The
guard in `mcp/sqlite-mcp-server.py` is the actual enforcement layer, and it is now exercised.

---

## Known remaining gaps

- **Stacked queries** (`SELECT ...; DROP ...`): the SELECT-only guard is a string-prefix heuristic
  and would not catch these. A read-only SQLite connection or a proper SQL parser (e.g. `sqlglot`)
  would be needed for production hardening.
- **Calibration disagreements (3 cases)**: two human-drift cases on the ambiguity criterion, one
  criterion non-observability bug. Unrelated to the router change.
