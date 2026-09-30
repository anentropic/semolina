---
phase: 52-core-object-semantics
status: complete
requirements: [CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06, CORE-07, CORE-08, CORE-09, CORE-10, CORE-11, CORE-12]
date: 2026-09-30
---

# Phase 52 Summary: Core Object Semantics

Six plans, each a test-first pair: the failing tests (or, for 52-05, strict xfails as the
roadmap specified) in one commit, the fix in the next. Phase 52.1 was inserted between 52-02
and 52-03 and is recorded in its own summary.

| Plan | Tests | Fix | Requirements |
|------|-------|-----|--------------|
| 52-01 `Row` | `0bf7af6` | `3d749c2` | CORE-01, CORE-02 |
| 52-02 equality | `fcc8e03` | `ba2fee8` | CORE-03 |
| 52-03 `in_()`, engine validation, duplicates | `a4f1e7e` | `f8d62f2` | CORE-05, CORE-06, CORE-10 |
| 52-04 cursor parity | `67f4836` | `3306d29` | CORE-07, CORE-08, CORE-09, CORE-12 |
| 52-05 DTO date/datetime | `5dc8ef6` | `f0d5d37` | CORE-11 |
| 52-06 model inheritance | `84cad5b`, `bcb715f` | `80e0429`, `f036f87` | CORE-04 |

Every fix after Phase 52.1 was mutation-checked: each part of it broken on purpose, and the
new tests required to fail. 52-03 killed 12 of 12, 52-04 27 of 27, 52-05 3 of 3; 52-06's one
survivor (a three-level chain) got its own test and was then killed.

## What each requirement got

**CORE-01/02 — `Row`.** Copies, deep-copies and pickles; hashable; has `.get()`; is a
`Mapping`. A column that collides with a method name is reached by item access, documented.

**CORE-03 — equality.** `OrderTerm` and the query compare fields by identity, so queries
over different fields are unequal. The tautological assertions that passed for any field
were rewritten.

**CORE-04 — inheritance (D1: support it, with `abstract = True` bases).** A concrete subclass
names its own view and inherits its parents' fields along the MRO, nearest base winning.
Each inherited field is copied and re-bound to the subclass, so its queries read its own
view. A redeclared field replaces the inherited one; any other attribute of that name
removes it. `abstract=True` bases name no view, list their fields, and refuse `.query()`;
`SemanticView` itself refuses the same way. `how-to/models.rst` gained "Share fields between
models". Copilot's review of PR #43 then found that a field removed by a subclass came back
one level further down, because the walk merged each base's `_fields` and a removal leaves
nothing there. The walk now reads every class dictionary in reverse MRO (`bcb715f`,
`f036f87`), so a plain mixin's fields count too. The same review's second finding, a sync
finalizer leaking a slot while a reader is open, did not reproduce: the busy guard exists
only in poolhouse's async pool.

**CORE-05 — `in_()`.** `In` copies its values into a tuple when built and refuses a string,
bytes, or a non-iterable, so `in_("US")` no longer becomes `IN ('U', 'S')` and a generator
binds every placeholder.

**CORE-06 — empty query.** `Engine.execute()` and `AsyncEngine.aexecute()` validate before
building SQL or taking a connection: `ValueError`, not the builder's `AssertionError`.

**CORE-07 — sync `close()`.** Mirrors `aclose()`: reader, cursor, connection; narrow
suppression; a `ResourceWarning` for a slot that cannot be returned; idempotent.

**CORE-08 — one read per cursor.** Wider than the requirement's wording. The first read
claims the result; the DBAPI fetches share one claim; any other read raises the new
`SemolinaResultConsumedError` naming both calls. This withdrew one documented async
behaviour, `fetch_record_batch()` then iteration sharing a reader, which now raises too.

**CORE-09 — pyarrow.** Every row method on both cursors names `semolina[pyarrow]` when it
is missing. Extras decision: `snowflake` and `databricks` compose `semolina[pyarrow]`, since
ADBC reads every row through a pyarrow reader.

**CORE-10 — duplicates.** Selecting a field twice raises in the builder; every Row method
refuses a result whose column names repeat.

**CORE-11 — timestamp into `date`.** The fast-path schema check refuses it, as Pydantic's
`validate=True` path already did.

**CORE-12 — bookkeeping.** The dead `pool` argument is gone from both cursors; the sync
reader is recorded and closed.

## Left open

- `semolina codegen --check` reads model files as text and does not follow base classes,
  so it reports an inherited field as absent. Documented; generated models never inherit.
  Resolving bases across files would be a codegen change, not a Phase 52 one.
- Three async streaming tests and the async repr tests leave fake cursors unclosed and
  trigger "garbage collected without being closed" warnings. Measured as unchanged from
  before 52-04.
