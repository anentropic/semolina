# Gap Detection Report

**Source root:** src/
**Language:** python
**Doc set:** 28 hand-written `.rst` files under `docs/src/` (excluding the sphinx-autoapi-generated `docs/src/reference/api/`)

**Total exported symbols:** 34 (union of `__all__` in `semolina/__init__.py`, `semolina/engines/__init__.py`, `semolina/exceptions.py`)
**Documented symbols:** 31 (91%)
**Undocumented symbols:** 3

## Undocumented Exports

| Symbol | File | Type | Assessment |
|--------|------|------|------------|
| `Dialect` | `src/semolina/__init__.py` | `StrEnum` | **Regression introduced by the how-to consolidation.** Its only narrative mention lived in `how-to/backends/overview.rst`, which was deleted in the 17→12 merge. That page explained that a `.semolina.toml` `type` value is a member of the `Dialect` enum, which is what makes `"snowflake"`, `"databricks"`, `"duckdb"` the accepted set. `how-to/backends.rst` shows `type` in three TOML examples and in all three per-backend field tables ("Must be ``"snowflake"``"), so a reader can still infer the values — but the canonical source is no longer named, and a public export now has zero narrative coverage. Worth a one-sentence restore. |
| `DialectABC` | `src/semolina/engines/__init__.py` | abstract class | Extension point for third-party dialect authors. Covered by sphinx-autoapi reference; no narrative page targets that audience. Unchanged from the previous audit. |
| `_require` | `src/semolina/exceptions.py` | function | Underscore-prefixed, deliberately in `__all__` to declare the module's own interface. Internal by convention — not a documentation gap. |

## Notes

Coverage of the user-facing import surface remains effectively complete: all 25 names in the
top-level `semolina.__all__` that a reader actually imports are named in at least one
narrative page.

Composition changed since the previous audit. `DuckDBDialect` was undocumented then and is
covered now — the merged `how-to/backends.rst` names it. `Dialect` moved the other way, for
the reason given above. Net count is unchanged at 3, which is why a count-only comparison
would have missed both movements.

`DialectABC` and `_require` are the same two structural non-gaps recorded previously. Neither
is reachable from a task in `config.yaml`'s `user_tasks` for either persona.
