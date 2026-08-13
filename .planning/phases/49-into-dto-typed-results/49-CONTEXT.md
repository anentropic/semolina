# Phase 49: `.into(DTO)` Typed Results - Context

**Gathered:** 2026-08-13
**Status:** Ready for planning

<domain>
## Phase Boundary

What an **already-executed result** can be turned into: typed Python objects via arrowmodel,
and pandas/polars dataframes. Nothing about how the query is built, and nothing about
generating the DTO class — that is Phase 50 (DTO-07/08/09), which consumes the `.into()`
surface this phase defines.

Requirements: DTO-01, DTO-02, DTO-03, DTO-04, DTO-05, DTO-06, RESULT-01, RESULT-02.

</domain>

<decisions>
## Implementation Decisions

### Conversion path

- **D-01:** arrowmodel's **fast path is the default**. `.into(DTO)` converts via
  `model_construct` with no per-value validation. `.into(DTO, validate=True)` passes the
  keyword straight through to arrowmodel's own `convert(validate=)`, which serialises each
  row to JSON in Rust and runs `model_validate_json` (2–5x slower, raises pydantic
  `ValidationError` naming the field, stops at the first failing row).
  Verified against `https://anentropic.github.io/arrowmodel/how-to/use-validated-mode.html`.
  — **Reversibility:** costly — the default is a published behavioural contract; flipping it
  later silently changes performance and error behaviour for every existing `.into()` call
  site.

- **D-02:** `.into()` lives on **`SemolinaCursor` and `AsyncSemolinaCursor` only**. No
  `Query.into()` terminal. One rule everywhere: execute, then shape — consistent with every
  existing result-shaping method and with the roadmap's "on a result" wording. A `Query`
  terminal would be purely additive if ever wanted later.
  — **Reversibility:** reversible — adding a `Query` terminal later breaks nothing.

### Streaming shape

- **D-03:** The streaming form **converts a whole batch at a time** (that is where
  arrowmodel's Rust speed comes from) but **yields DTO instances individually**, exactly
  mirroring the existing `for row in cursor`. Batching is an internal detail the caller never
  sees. Explicitly NOT `list[DTO]`-per-batch — an initial selection of the batched form was
  reversed in discussion.

- **D-04:** It is called **`iter_into(DTO)`** — verb-first, matching the cursor's existing
  `fetch_arrow_table` / `fetch_record_batch` / `fetchall_rows` family. `.into()` keeps its
  roadmap-given name for the eager form.
  — **Reversibility:** one-way — a public method name on the primary result surface, used in
  DTO-06's docs and consumed by Phase 50; renaming after release breaks user code and the
  published examples.

- **D-05:** `iter_into()` **raises at the call, not on first iteration**. It is a regular
  method that runs the pre-check and then returns a generator — NOT a generator function,
  whose body would not run until the first `next()`. Same on the async cursor, where it stays
  a plain method returning an async iterator (consistent with Phase 46 keeping `__aiter__`
  plain while `fetch_record_batch` is `async def`).
  Taken as Claude's discretion, not a user decision — see Claude's Discretion below for why.

### Schema pre-check (this is how DTO-03 is satisfied)

The fast path uses `model_construct` and therefore raises nothing on a type mismatch — it
produces precisely the "silent wrong-typed value" DTO-03 exists to prevent. DTO-03 is
therefore satisfied by a **structural pre-check**, not by arrowmodel.

- **D-06:** The pre-check **runs always**, on both `.into()` and `iter_into()`, and needs
  **no probe and no round trip**. It reads the Arrow schema already in memory:
  `pyarrow.Table.schema` for the eager path, `RecordBatchReader.schema` for streaming (the
  Arrow C stream delivers the schema when the stream is established, before any batch moves;
  poolhouse documents its async reader's `.schema` as "synchronous; no offload — touches no
  I/O"). This is what the roadmap's "Settled going in" already anticipated: *"`.into(DTO)`
  needs no probe — the executed result already carries its Arrow schema."*

- **D-07:** Result columns the DTO does not declare are **ignored**. The DTO is a projection
  of the result, so one DTO can serve several queries and a query can gain a column without
  breaking existing DTOs. Matches arrowmodel's name-matching, which already drops unclaimed
  columns.

- **D-08:** A DTO field with **no matching result column is an error, unless the field has a
  default** (including `= None`). Defaults are honoured as "optional in the result".

- **D-09:** **Nullability is not checked at all.** Decided on evidence rather than preference:
  `47-DECISIONS.md` measured the Arrow nullable flag as `True` for all seven DuckDB fields
  *including COUNT*, so treating "result nullable, DTO field not `| None`" as a mismatch
  would flag essentially every field on every query. The flag carries no information. The
  pre-check compares base types only and says nothing about nullability.

- **D-10:** Type comparison is **subtype-tolerant**: it passes when the DTO's annotation can
  legally hold the Python type `arrow_type_to_python` derives from the Arrow type. So `Any`
  and `object` are a deliberate opt-out rather than an error, an exact match obviously passes,
  and `decimal.Decimal` arriving where the DTO declared `float` stays a hard failure — the
  case Phase 47's whole Decimal policy exists for. Note the check has **no values to
  `isinstance` against**, because no rows are fetched; it resolves and compares types.

- **D-11:** The error **reports every mismatched field at once**, not just the first. Unlike
  arrowmodel's validated path, which stops at the first bad row because it is streaming
  values, the pre-check holds the entire schema up front, so listing all of them costs nothing
  and saves a fix-one-rerun cycle per field.

### Optional dependencies and errors

- **D-12:** **Four extras**, one install idiom: `[pyarrow]`, `[pandas]`, `[polars]`,
  `[arrowmodel]`, joining the existing `[async]` / `[duckdb]` / backend extras. Every missing
  package is fixed the same way — `pip install semolina[polars]`. Accepted cost: Semolina
  pins versions for pandas and polars, which it never imports (the ADBC driver does — poolhouse
  states "pandas is not a poolhouse dependency … poolhouse never imports it"). Side benefit:
  pandas currently arrives only *transitively* via `snowflake-connector-python` /
  `databricks-sql-connector`, which is the root of WINDOWS.md broken window 3; an explicit
  extra makes it declared rather than accidental.
  — **Reversibility:** costly — published extras are an install contract; removing one breaks
  existing `pip install semolina[...]` lines in user CI.

- **D-13:** **`[all]` means all** — it gains all four new extras. An initial "keep `all` to
  backends + async" selection was reversed in discussion. Consequence to exploit deliberately:
  this project's CI runs `uv sync --all-groups --extra all`, so **polars lands in the test
  environment**, which is what makes D-16 possible.

- **D-14:** **Two new flat exceptions** in a NEW `src/semolina/exceptions.py`, exported from
  the package root: `SemolinaMissingDependencyError(RuntimeError)` and
  `SemolinaSchemaMismatchError(RuntimeError)`. The existing `SemolinaViewNotFoundError` /
  `SemolinaConnectionError` stay in `engines/base.py` **untouched** — no `SemolinaError` base
  class, no reparenting. Nothing outside this phase's scope changes.

- **D-15:** **pyarrow gets the same guard**, and this is in scope. Grounded finding from the
  discussion: ADBC's dbapi guards its own pyarrow import (`_has_pyarrow`) and Semolina declares
  `pyarrow` **only inside the `[duckdb]` extra** — not base, not `[snowflake]`, not
  `[databricks]` — so a base install plus a warehouse extra can already reach
  `fetch_arrow_table()` and fail obscurely today. Guarded methods: `fetch_arrow_table`,
  `fetch_record_batch`, `fetch_df`, `fetch_polars`, on **both** cursors. `[duckdb]`'s existing
  `pyarrow>=17.0.0` pin can reference the new extra rather than duplicate it.

### Inherited evidence gap

- **D-16:** **Assumption A3 (polars Decimal support) gets measured and closed in this phase.**
  `47-DECISIONS.md` states it outright: *"It is Phase 49's problem via `fetch_polars()`, and it
  is an open assumption here rather than an answer."* It was blocked only because polars was
  not installed; D-13 fixes that. Run the same measurement Phase 47 ran for pandas (which
  measured `to_pandas()` rendering `decimal128` as an `object` dtype holding `decimal.Decimal`
  at pandas 2.3.3), put the real row in `47-TYPE-FIDELITY.md`, and let the measured answer
  decide whether `fetch_polars()` needs a documented caveat. `tests/type_fidelity_probe.py`'s
  `_measure_polars()` currently hard-codes the `not measured` row and must actually measure.

- **D-17:** Closing A3 makes a sentence in `47-DECISIONS.md` stale. Handle it with a **dated
  in-body correction** beneath the original text — not a rewrite, and not silence. The doc
  stays a truthful record of what was decided on what evidence, while a reader cannot act on
  the stale line. This follows the `46-VERIFICATION.md` precedent rather than Phase 48's D-10
  (which left `47-DECISIONS.md` entirely untouched); the difference is that D-10 superseded
  *cell values in a generated artifact*, whereas this supersedes *a normative claim about
  what is known*.

### Claude's Discretion

- **D-05's fail-fast timing** was taken as discretion rather than a user decision. The
  question as first posed implied a cost that does not exist: reading `reader.schema` pulls no
  batch and issues no query, so both options cost the same and one is strictly better.
  Recorded because the *implementation* consequence is non-obvious — `iter_into` must not be
  written as a bare generator function.
- **D-11's report-all-at-once**, same reasoning: free, given the whole schema is in hand.
- **Detection mechanism** for missing packages. Precedent to follow:
  Phase 47 used `importlib.util.find_spec` specifically so that polars is never imported.
- **DTO-06's docs shape** — whether the worked BI-backend example is a how-to or a tutorial,
  and what the scenario is. Follow `.claude/skills/semolina-docs-author/SKILL.md` (mandatory
  for docs work per CLAUDE.md); the Diataxis classification decides it.
- **arrowmodel version floor** — not installed, absent from `pyproject.toml`; pick a floor.

### Folded Todos

- **`.planning/todos/pending/2026-07-10-arrowmodel-result-serialization-integration.md`**
  (`resolves_phase: 49`) — the origin analysis for DTO-01–06. Its "delivery level 1" (document
  the passthrough, no new code) is **superseded**: this phase ships a real `.into()` surface,
  not a docs-only integration. Its level 2 (dynamic `create_model`) stays out of scope per the
  roadmap; level 3 is Phase 50. Its scrutiny section — derive the DTO from the query, not from
  the `SemanticView` model, and not from Databricks materializations (rejected) — still stands.
  Retire this todo when the phase closes.
- **`.planning/todos/pending/2026-05-15-fetch-df-and-fetch-polars-adbc-passthrough.md`**
  (`resolves_phase: 49`) — RESULT-01/02. Its acceptance list is largely satisfied upstream
  already (see Existing Code Insights); the open part is the actionable error, which is D-12/
  D-14/D-15. Note its ask to "update `docs/src/how-to/arrow-output.rst` to prefer these where
  applicable". Retire when the phase closes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Normative type policy (binding on this phase)
- `.planning/phases/47-type-fidelity-probe-decision-doc/47-DECISIONS.md` — the Decimal policy,
  the metric-nullability stance, and result-schema-primary. **Decision 1 is a prohibition**:
  the Decimal policy is annotation-only, `batch.to_pylist()` feeding `Row(...)` at
  `cursor.py:281` is the whole value path and carries no coercion. Read its "polars" bullet
  under Decision 1 — that is D-16's subject.
- `.planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md` §"Downstream
  Decimal behaviour" — the pandas row (measured) and the polars row (`not measured`, A3).
  This artifact is regenerated by D-16.

### External library docs (verify against these, do not infer)
- `https://anentropic.github.io/arrowmodel/` — `ArrowModel`, `X.convert(batch)`, accepted
  Arrow inputs (RecordBatch / Table / any Arrow-PyCapsule input), nested Struct → nested
  model, alias resolution.
- `https://anentropic.github.io/arrowmodel/how-to/use-validated-mode.html` — the `validate=`
  keyword, fast vs validated path semantics, the `ValidationError` shape. D-01 rests on this.

### Origin analysis
- `.planning/todos/pending/2026-07-10-arrowmodel-result-serialization-integration.md` — why
  the DTO derives from the query rather than the model or a Databricks materialization.
- `.planning/todos/pending/2026-05-15-fetch-df-and-fetch-polars-adbc-passthrough.md` — the
  RESULT-01 acceptance list.

### Project standards
- `CLAUDE.md` — quality gates (`prek run --all-files`, `just test` — **two** suites, root and
  jaffle-shop — and `just docs-build`), the no-`# type: ignore` rule, and the bug-fix protocol
  (failing test first, then the fix).
- `.claude/skills/semolina-docs-author/SKILL.md` — **mandatory** for DTO-06's docs work.
- `.planning/WINDOWS.md` — entry 3 (pandas row environment-dependent) is touched by D-12.

**Stale, do not trust:** `.planning/codebase/*.md` are dated 2026-02-17 and still describe the
package as `cubano`, with `MockEngine` and the pre-v0.3 pool registry. CONVENTIONS.md is still
usable for *style* (docstring shape, `TYPE_CHECKING` guards, `__all__` discipline, error-message
tone); ARCHITECTURE.md is not usable for structure — read the source.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`src/semolina/codegen/arrow_map.py::arrow_type_to_python`** (Phase 48) — maps an Arrow
  type to a Python type, predicate-based on `pyarrow.types.is_*`. This is exactly what the
  D-06 pre-check needs. Directly reusable.
- **`src/semolina/codegen/annotation_check.py`** (Phase 48) — the per-field comparison design
  precedent (`FieldCheckRow`, `ViewCheckReport`), **but not a drop-in**: it is probe-driven
  and shaped around `IntrospectedView`/codegen models. `.into()` needs no probe.
- **`src/semolina/types.py::JsonValue`** (Phase 48) — a VARIANT column reaching a DTO field is
  the untested case for the pre-check.
- **`tests/type_fidelity_probe.py::_measure_polars`** — currently returns the hard-coded
  `not measured` row; D-16 replaces it with a real measurement.

### Established Patterns

- **ADBC passthrough** (Phase 39): result shaping delegates to ADBC rather than
  reimplementing. `fetch_arrow_table` / `fetch_record_batch` are two-line delegates with long
  docstrings carrying the lifetime rules.
- **`TYPE_CHECKING`-only optional imports**: `cursor.py` imports `pyarrow` under
  `TYPE_CHECKING` with `from __future__ import annotations`. The pattern for arrowmodel,
  pandas and polars.
- **Errors**: `Semolina*Error(RuntimeError)`, flat, exported from the package root; messages
  name the received value and suggest the correct alternative (CONVENTIONS.md).
- **Reader lifetime** (Phase 46, `acursor.py` docstrings): one reader per cursor; a repeat
  `fetch_record_batch()` returns the reader already in flight; closing out of order raises
  `ConnectionBusyError`; the cursor keeps the reader so `aclose()` can close it. `iter_into`
  drives that same single stream — **pick one consumption pattern per cursor**, because a
  second consumer picks up where the first stopped. The async cursor has **no `__del__`
  rescue**, so an unclosed async cursor leaks a pool slot permanently.

### Integration Points

- **`src/semolina/cursor.py`** — `.into()`, `iter_into()`, `fetch_df()`, `fetch_polars()`;
  guards on the four Arrow/dataframe methods.
- **`src/semolina/acursor.py`** — the async twins. `fetch_record_batch` returns `Any` there
  because poolhouse's reader class is not a public importable name.
- **`src/semolina/exceptions.py`** — new (D-14).
- **`src/semolina/__init__.py`** — export the two new errors.
- **`pyproject.toml`** — four new extras, `[all]` recomposed, arrowmodel floor.

### Already implemented upstream — do NOT reimplement

`fetch_df()` and `fetch_polars()` **already exist on both layers**:
`adbc_driver_manager.dbapi.Cursor` (1.10.0) and `adbc_poolhouse._async._cursor.AsyncCursor`
(which offloads them through the pool limiter with cancellation and poison recovery). RESULT-01
is four passthrough methods.

**RESULT-02 is the actual work there**, because both layers deliberately refuse it — poolhouse:
*"poolhouse never imports it: the driver imports `pandas` inside the worker, so a missing
install surfaces the native `ModuleNotFoundError` unchanged, with no pre-check and no
wrapping."* ADBC's `fetch_polars` does a bare `import polars`.

</code_context>

<specifics>
## Specific Ideas

- **DTO-05's premise was false and has been corrected before planning.** The requirement
  promised that a default install pulls no pydantic. It always has:
  `semolina` → `adbc-poolhouse` → `pydantic-settings>=2.0.0` → `pydantic>=2.7.0`, unconditional
  since v0.3. The `[arrowmodel]` extra gates arrowmodel alone. REQUIREMENTS.md and ROADMAP.md
  SC5 amended in commit `f87290f` — plan against the amended text.

- **The pre-check must not become value coercion.** `.into()` validating a *schema* is not
  licence to revisit `Row` construction. See the Reviewed Todos below and 47-DECISIONS.md
  Decision 1, which names a change to `cursor.py`/`results.py` as inverting the decision.

- **Two questions deliberately left to research rather than decided:**
  1. Does arrowmodel itself tolerate a declared field with no matching Arrow column, or does
     it error first? If it errors, D-08's default-allowance only relocates the failure and the
     decision needs revisiting.
  2. How are the absent-package paths tested, now that D-13 makes CI install everything? A real
     uninstall is not available; Phase 47's `find_spec`-monkeypatch shape is the precedent.

</specifics>

<deferred>
## Deferred Ideas

- **`Query.into(DTO)` eager terminal** — considered and rejected for this phase (D-02). Purely
  additive; can land later without breaking anything if the DTO-06 docs example reads clumsily.
- **`list[DTO]`-per-batch streaming (`into_batches`)** — considered and rejected (D-03).
- **`SemolinaError` common base class** — considered and rejected (D-14). Would give app
  backends one `except` clause, and would be backward compatible, but it touches errors outside
  this phase.
- **Making `pyarrow` a base dependency** — considered and rejected in favour of the guard
  (D-15). Semolina is Arrow-native in practice, so this may be worth revisiting as a
  project-level dependency decision.
- **STREAM-04, user-controllable batch size** — already deferred to a later milestone in
  STATE.md's deferred-items table. Streaming batch size stays whatever the driver picks.
- **`cursor.into(DTO, check=False)` escape hatch** for skipping the pre-check in a tight loop —
  raised, not pursued; the check is one comparison per result.

### Reviewed Todos (not folded)

- **`2026-02-25-runtime-type-coercion-validation-on-row-construction.md`** — **reviewed and
  deliberately NOT folded.** It asks for exactly the `Row`-construction type coercion that
  Phase 47 Decision 1 prohibits. It is listed here so that nobody reads this phase's `.into()`
  validation as licence to revisit it. Still deferred.
- **`2026-02-18-dataframe-agnostic-result-output-via-arrow.md`** — largely superseded. Its open
  question ("is Arrow the right interchange?") was answered yes in v0.4.0, and narwhals is in
  PROJECT.md's Out of Scope. RESULT-01 closes the practical remainder.
- **`2026-02-23-lazy-streaming-result-with-cursor-based-iteration.md`** — superseded by Phase 39
  (`fetch_record_batch()` plus lazy `__iter__`).
- The remaining `todo.match-phase` hits (CLI query interface, GraphQL, MCP tools, FastAPI /
  django-ninja integrations, auth schemes, jaffle-shop→Databricks) scored on generic keywords
  only and are unrelated to this phase.

</deferred>

---

*Phase: 49-into-dto-typed-results*
*Context gathered: 2026-08-13*
