# Phase 48: Type Map Implementation & Databricks Literals - Context

**Gathered:** 2026-08-12
**Status:** Ready for planning
**Source:** Plan-phase orchestrator session. The user declined `/gsd-discuss-phase` on the
grounds that `47-DECISIONS.md` is already this phase's normative specification, then answered
four scoping questions raised by `48-RESEARCH.md`. This file records those answers plus the
researcher recommendations adopted as routine judgment calls. It does not restate
`47-DECISIONS.md` — read that document directly; it outranks this one.

<domain>
## Phase Boundary

Generated models carry the types `47-DECISIONS.md` specifies, identically across Snowflake,
Databricks, and DuckDB, and Databricks filters accept `date` / `datetime` / `Decimal` values.
Covers TYPE-03, TYPE-04, TYPE-05, TYPE-06, TYPE-07, DBX-04.

Fixed by ROADMAP.md. This is an implementation phase for a design decided upstream — the job
is mechanics and fallout, not re-litigating Phase 47's decisions.

</domain>

<decisions>
## Implementation Decisions

### Scope of Decision 3 (result-schema-primary)

- **D-01:** *(user, this session)* `semolina codegen --check` resolves annotations from the
  **result schema** (`adbc_execute_schema`, with the zero-row wrapper as fallback). The
  `semolina codegen` **generation** path is **unchanged** — it keeps building models from
  warehouse metadata (`DESCRIBE SEMANTIC VIEW` / `SHOW COLUMNS IN VIEW` /
  `DESCRIBE TABLE EXTENDED AS JSON`), now feeding the corrected type map. Decision 3's
  promotion of the probe route inside *generation* is Phase 50's DTO-07/DTO-09, not this
  phase's work. This closes `48-RESEARCH.md` Assumption A1 and open question 2.

  **Do not** build in this phase: a canonical-query builder for the generation path, an
  offline/metadata fallback chain inside generation, or per-annotation route recording in
  emitted model source. Those are Phase 50.

- **D-02:** *(user, this session)* The consequence is accepted and must be **documented, not
  suppressed**: immediately after `semolina codegen` writes a model, `semolina codegen --check`
  on the same view may report drift for any type where the metadata route and the probe route
  still disagree. That divergence is Phase 47's central finding; surfacing it is the point.
  The user explicitly declined the alternative of adding a metadata-vs-probe equality test to
  make the disagreement impossible.

### TYPE-05 / TYPE-06 annotation contract

- **D-03:** *(user, this session)* Annotate **the measured value**, not the semantic type. The
  annotation names what the user actually holds in a `Row`. Measured through the real ADBC
  path on duckdb 1.5.5 / pyarrow 24.0.0 (`48-RESEARCH.md` § "The DuckDB map gaps, measured"):

  | DuckDB type | Annotation | Note |
  |---|---|---|
  | `DECIMAL(p,s)` | `decimal.Decimal` | locked by 47-DECISIONS.md Decision 1 |
  | `UUID` | `str` | **not** `uuid.UUID` — the value is a `str` |
  | `JSON` | `str` | raw JSON text, unparsed |
  | `ENUM(...)` | `str` | arrives as `str` from a dictionary-encoded column |
  | `TIMESTAMP_S` / `TIMESTAMP_MS` | `datetime.datetime` | |
  | `TIMESTAMP_NS` | `datetime.datetime` | sound over-approximation; the value is
  `pandas.Timestamp` (a `datetime.datetime` subclass) when pandas is importable |

  Preserve the raw warehouse type in a comment or docstring so the information is not lost.
  Annotating `uuid.UUID` or a parsed JSON type was rejected: it would recreate exactly the
  annotation-vs-value defect Decision 1 exists to end, and would make Phase 47's own fidelity
  artifact score those rows `mismatch`. Closes `48-RESEARCH.md` open question 1 and A2/A3.

- **D-04:** *(user, this session)* `TIMESTAMP_NS`'s environment dependence is documented, not
  hidden — without pandas the value truncates to microseconds, and raises `ValueError` on
  sub-microsecond input (pyarrow 24.0.0 `scalar.pxi:706-725`). This is broken window 3.

### Mappings already wrong, outside the requirement set

- **D-05:** *(user, this session)* Fix DuckDB `HUGEINT`: `int` → `decimal.Decimal`. The value
  arrives as `decimal.Decimal` (Arrow `decimal128(38, 0)`); it is the Decimal policy applied
  consistently, and leaving it as `int` makes TYPE-03's "the three backends no longer disagree
  about money" read false.

- **D-06:** *(user, this session)* Do **not** fix DuckDB `INTERVAL` (annotated
  `datetime.timedelta`, value is `pyarrow.MonthDayNano`). No stdlib type describes
  `MonthDayNano`, so choosing one is a design question this phase's spec does not cover.
  Record it as a broken window (`.planning/WINDOWS.md`) with the measurement, and leave the
  mapping alone. Closes `48-RESEARCH.md` open question 7.

### Adopted researcher recommendations (orchestrator judgment, not user-stated)

These were `48-RESEARCH.md` open questions 3–6. The researcher's recommendation is adopted in
each case; each is a routine call, and each is recorded here so a reviewer can see it was a
choice rather than an oversight.

- **D-07:** Widen **both** `Dialect.render_literal` (base) and `DatabricksDialect.render_literal`
  for `date` / `datetime` / `Decimal`. The base is the documented single audited escaping site,
  it is symmetric, and `TestRenderLiteralStandardSql` already exercises it. (Open question 4.)

- **D-08:** For aware `datetime` on Databricks, **normalise to UTC and emit `TIMESTAMP '…Z'`**.
  `Z` is unambiguously listed in the Databricks literal grammar; the bare `+hh:mm` offset form
  produced contradictory readings of the same doc page (`48-RESEARCH.md` A6). Same instant, no
  ambiguity. (Open question 5.)

- **D-09:** `--check`'s **verifiable acceptance is scoped to DuckDB (live) and Snowflake
  (cassette)**. Databricks is recorded as evidence-limited, exactly as Phase 47 did in the same
  situation: it has no `ExecuteSchema`, and nobody has confirmed its metric-view planner accepts
  the `WHERE 1=0` wrapper (broken window 2, still open; todo
  `.planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md`). **Do not write
  an acceptance criterion nobody can run.** (Open question 6.)

- **D-10:** Phase 47's artifact and canary: regenerate and commit `47-TYPE-FIDELITY.md` (its
  `test_committed_table_is_not_stale` guard forces this), and **re-point** the circularity canary
  at `tests/unit/test_type_fidelity_duckdb.py:126` — currently asserting `"TODO: DECIMAL(38,2)"`
  — at `STRUCT`/`MAP`/`LIST`, adding a positive "agrees by value" twin for the decimal case.
  **Deleting the canary to get green destroys the guard**; it is designed to fail when the
  columns agree. Leave `47-DECISIONS.md` untouched and note the supersession in Phase 48's own
  summary. (Open question 3.)

</decisions>

<specifics>
## Specific Requirements

- `probe_schema` / `ProbeResult` move from `tests/type_fidelity_probe.py` into `src/` (the
  researcher's option (a) — promote, then have the test module import it), so a shipped
  `--check` and the evidence generator cannot drift. Add a test asserting the promoted module
  does **not** import `semolina.codegen.type_map`, preserving Phase 47's anti-circularity
  defence at its new location. After the move, `47-TYPE-FIDELITY.md` must still regenerate
  byte-identical.
- A new `arrow_type_to_python(pyarrow.DataType) -> str` is required — no such function exists
  in the repo. Build it on `pyarrow.types.is_*` predicates, **not** on `str(dtype)`: the string
  forms (`decimal128(38, 2)`, `timestamp[us, tz=Europe/London]`,
  `dictionary<values=string, indices=uint8, ordered=0>`) do not survive naive matching. Phase
  50's DTO-07 needs the same function, so build it as a first-class tested module rather than a
  private CLI helper.
- Re-read `adbc-drivers/databricks` `go/statement.go` at the pinned version **as the first task
  of the `--check` work**. Decision 4 gave its "no `ExecuteSchema`" row a seven-day shelf life
  from 2026-08-12; that window has expired (`48-RESEARCH.md` A10).
- `just docs-build` must stay clean; `docs/src/explanation/type-fidelity.rst` lines 152-165 carry
  a `.. note::` that becomes **false** the moment this phase lands, and
  `docs/src/how-to/codegen.rst` needs the new exit code, a `--check` section, and a correction to
  its VARIANT claim.

</specifics>

<canonical_refs>
## Canonical References

- `.planning/phases/47-type-fidelity-probe-decision-doc/47-DECISIONS.md` — **normative**. The
  specification for this phase. Do not edit it; Phase 48 changes code, not the decision.
- `.planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md` — the measured
  evidence; regenerated by this phase (D-10).
- `.planning/phases/48-type-map-implementation-databricks-literals/48-RESEARCH.md` — mechanics,
  exact identifiers, line numbers, the measured DuckDB table, and seven pitfalls.
- `@.claude/skills/semolina-docs-author/SKILL.md` — **mandatory** for any plan touching
  `docs/src/`.
- `.planning/WINDOWS.md` — broken windows 2 (Databricks zero-row wrapper unverified) and 3
  (pandas-dependent `TIMESTAMP_NS`).

</canonical_refs>

<scope_fence>
## Scope Fence — verified against current code

`47-DECISIONS.md` states the Decimal policy is **annotation-only**, as a prohibition.
`48-RESEARCH.md` re-verified it this session rather than inheriting it:
`src/semolina/cursor.py:281` is verbatim `self._batch_rows = batch.to_pylist()`, and a fresh
grep for `Decimal(` / `float(` / `int(` across `cursor.py`, `acursor.py`, and `results.py`
returns only a docstring false positive.

**Phase 48 must NOT modify `src/semolina/cursor.py`, `src/semolina/acursor.py`, or
`src/semolina/results.py`.** No value coercion is added anywhere. The phase changes what the
type map *says* and what `render_literal` *emits*, never what a `Row` *holds*.

This belongs in `must_haves.prohibitions`, with a runnable git gate (`48-RESEARCH.md` supplies
one).

</scope_fence>

<deferred>
## Deferred Ideas

- **Probe-primary *generation*** — canonical-query builder, metadata fallback chain, and route
  recording in emitted source. Phase 50, DTO-07/DTO-09 (D-01).
- **DuckDB `INTERVAL` → a correct Python annotation** — needs a design answer for
  `pyarrow.MonthDayNano`. Logged as a broken window, not fixed here (D-06).
- **Databricks `--check`** — blocked on someone running the `WHERE 1=0` wrapper against a live
  metric view. Existing todo, existing broken window (D-09).
- **Value coercion of any kind** — permanently out of scope for this phase by the fence above;
  a future phase would have to revisit 47-DECISIONS.md to introduce it.

</deferred>

---

*Phase: 48-type-map-implementation-databricks-literals*
*Context recorded: 2026-08-12 (plan-phase session, not discuss-phase)*
