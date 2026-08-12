---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 1
total_count: 2
last_updated: 2026-08-12T00:02:53.283Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 46 | deviation | docs/src/how-to/web-api.rst |  | Async cancellation/timeout/client-disconnect sections of docs/src/how-to/web-api.rst are still unwritten. Both blockers are now gone and only the writing remains. Blocker 1 (adbc-poolhouse cancelled-query deadlock) was fixed in 1.6.2 and the floor moved to it. Blocker 2 (semantic_view() ran its inner query on a new ClientContext, so it never read the interrupt flag adbc_cancel had set) was fixed in duckdb-semantic-views 0.12.0, published to the community CDN for DuckDB core 1.5.5 on 2026-08-11; the pin moved 1.5.3 -> 1.5.5 in the same change. Verified on one machine across both builds, interrupting at a tenth of the baseline: 0.10.3 returned at 3.22s of a 3.97s baseline (ran to completion), 0.12.0 returns at 0.55s of 3.21s. ASYNC-06's elapsed-time claim is now asserted on Semolina's own generated SQL in TestCancellationThroughAexecute, closing the verification gap; it is non-vacuous, since the old build fails the same assertion at 0.81 of baseline where the new one passes at 0.17. What is left is authoring the four sections with no caveat. | fixed |  | 2026-08-02T11:23:22.862Z | 2026-08-11T22:37:52.730Z |
| 2 | 47 | unrun-verify | tests/type_fidelity_probe.py |  | probe_schema's zero-row fallback branch has never fired against a driver that actually refuses ExecuteSchema — RESEARCH.md assumption A5 (Databricks metric-view planner accepting a WHERE 1=0 wrapper) remains unrun | open |  | 2026-08-12T00:02:53.283Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "46",
    "file": "docs/src/how-to/web-api.rst",
    "line": null,
    "description": "Async cancellation/timeout/client-disconnect sections of docs/src/how-to/web-api.rst are still unwritten. Both blockers are now gone and only the writing remains. Blocker 1 (adbc-poolhouse cancelled-query deadlock) was fixed in 1.6.2 and the floor moved to it. Blocker 2 (semantic_view() ran its inner query on a new ClientContext, so it never read the interrupt flag adbc_cancel had set) was fixed in duckdb-semantic-views 0.12.0, published to the community CDN for DuckDB core 1.5.5 on 2026-08-11; the pin moved 1.5.3 -> 1.5.5 in the same change. Verified on one machine across both builds, interrupting at a tenth of the baseline: 0.10.3 returned at 3.22s of a 3.97s baseline (ran to completion), 0.12.0 returns at 0.55s of 3.21s. ASYNC-06's elapsed-time claim is now asserted on Semolina's own generated SQL in TestCancellationThroughAexecute, closing the verification gap; it is non-vacuous, since the old build fails the same assertion at 0.81 of baseline where the new one passes at 0.17. What is left is authoring the four sections with no caveat.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-02T11:23:22.862Z",
    "resolved_at": "2026-08-11T22:37:52.730Z"
  },
  {
    "id": 2,
    "kind": "unrun-verify",
    "phase": "47",
    "file": "tests/type_fidelity_probe.py",
    "line": null,
    "description": "probe_schema's zero-row fallback branch has never fired against a driver that actually refuses ExecuteSchema — RESEARCH.md assumption A5 (Databricks metric-view planner accepting a WHERE 1=0 wrapper) remains unrun",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T00:02:53.283Z",
    "resolved_at": null
  }
]
````
