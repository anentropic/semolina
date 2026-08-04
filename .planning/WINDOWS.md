---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-08-02T11:23:22.862Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 46 | deviation | docs/src/how-to/web-api.rst |  | Async cancellation/timeout/client-disconnect sections of docs/src/how-to/web-api.rst are still unwritten. The original cause is gone: adbc-poolhouse 1.6.2 shipped with the cancelled-query deadlock fixed and the floor moved to it. What remains is a writing task whose content is blocked on a DuckDB limitation measured in Plan 05 — the semantic_views extension table function does not observe the outer interrupt flag, so a cancelled semantic_view() query runs to completion (3.42s) where the equivalent plain SQL aborts at 0.32s. Needs an upstream report against anentropic/duckdb-semantic-views plus a follow-up doc plan. | open |  | 2026-08-02T11:23:22.862Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "46",
    "file": "docs/src/how-to/web-api.rst",
    "line": null,
    "description": "Async cancellation/timeout/client-disconnect sections of docs/src/how-to/web-api.rst are still unwritten. The original cause is gone: adbc-poolhouse 1.6.2 shipped with the cancelled-query deadlock fixed and the floor moved to it. What remains is a writing task whose content is blocked on a DuckDB limitation measured in Plan 05 — the semantic_views extension table function does not observe the outer interrupt flag, so a cancelled semantic_view() query runs to completion (3.42s) where the equivalent plain SQL aborts at 0.32s. Needs an upstream report against anentropic/duckdb-semantic-views plus a follow-up doc plan.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-02T11:23:22.862Z",
    "resolved_at": null
  }
]
````
