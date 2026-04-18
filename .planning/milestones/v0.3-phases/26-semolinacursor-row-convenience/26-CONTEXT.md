# Phase 26: SemolinaCursor & Row Convenience - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning
**Source:** Inline conversation (assumptions review)

<domain>
## Phase Boundary

Phase 26 delivers SemolinaCursor as the return type of `.execute()`, replacing `Result` entirely. SemolinaCursor wraps an underlying DBAPI 2.0 cursor via delegation and adds Row convenience methods (`fetchall_rows`, `fetchmany_rows`, `fetchone_row`).

</domain>

<decisions>
## Implementation Decisions

### Return Type
- `execute()` returns `SemolinaCursor` — not `Result`
- `Result` class is removed entirely — no deprecation, no backward compat
- Clean break from v0.2 API

### MockPool / Production Separation
- **No isinstance(pool, MockPool) in production code** — the check in `query.py:422` must be removed
- MockCursor must not appear in the normal runtime interface anywhere
- If tests need mock behavior, use `unittest.mock.patch`
- Production `execute()` only speaks standard DBAPI 2.0: `cursor.execute(sql, params)`

### Row Convenience Methods
- `fetchall_rows()` returns `list[Row]`
- `fetchmany_rows(size)` returns `list[Row]`
- `fetchone_row()` returns `Row | None`
- Existing `Row` class (attribute + dict access) is reused from `results.py`

### Claude's Discretion
- Whether SemolinaCursor passes through native DBAPI methods (fetchall, fetchone, fetchmany) or only exposes the `_rows()` variants
- Whether `results.py` is kept (for `Row` only) or `Row` moves to `cursor.py`
- SemolinaCursor typing approach (Protocol for underlying cursor vs concrete types)
- How MockCursor adapts to standard `execute(sql, params)` interface (or whether tests patch instead)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 25 Implementation (source of truth for current state)
- `src/semolina/query.py` — Current execute() implementation with MockPool isinstance check to remove
- `src/semolina/pool.py` — MockPool/MockConnection/MockCursor classes
- `src/semolina/results.py` — Row class (to keep) and Result class (to remove)
- `src/semolina/registry.py` — get_pool() registry interface

### Architecture
- `.planning/research/ARCHITECTURE.md` — v0.3 architecture design (SemolinaCursor section)

</canonical_refs>

<specifics>
## Specific Ideas

- SemolinaCursor uses delegation (composition) not subclassing — MockCursor and ADBC cursors share no common base
- Row conversion: use cursor.description column names + fetchall() tuple rows → Row(dict(zip(columns, row)))
- The pattern already exists in query.py lines 427-429 — extract into SemolinaCursor

</specifics>

<deferred>
## Deferred Ideas

- Arrow-native fetch methods (fetch_arrow_table, fetch_record_batch) — Phase 27+
- Async cursor support — future milestone
- Real ADBC cursor integration testing — requires warehouse connection

</deferred>

---

*Phase: 26-semolinacursor-row-convenience*
*Context gathered: 2026-03-17 via inline conversation*
