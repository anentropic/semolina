# Phase 42: Codegen Field-Type Inference — Context

**Gathered:** 2026-06-09
**Status:** Ready for planning
**Source:** Captured from `/gsd-discuss-phase 42 --assumptions` discussion (assumptions surfaced + validated)

<domain>
## Phase Boundary

Codegen must emit the correct `Metric`/`Dimension`/`Fact` field type for every
column across all three backends. **Codebase exploration during discussion
established that the core inference is already implemented** — this phase is
*test coverage + reconciliation + one strictness change*, not greenfield feature
work.

What already exists (verified during discussion):
- `python_renderer.py:_field_class_for()` already maps `field_type` →
  `Metric`/`Fact`/`Dimension`. **There is no bare `Field()` emitter** anywhere.
- DuckDB (`engines/duckdb.py`) already parses `DESCRIBE SEMANTIC VIEW` for
  DIMENSION/METRIC/FACT. A committed e2e snapshot
  (`tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr`) already shows
  `Fact[int]()`, `Dimension[str]()`, `Metric[int]()`. Success criterion 1 is
  effectively already met (verify, don't rebuild).
- Snowflake (`engines/snowflake.py:336`) already reads `kind` from
  `SHOW COLUMNS IN VIEW`.
- Databricks (`engines/databricks.py:336`) already reads `is_measure` from
  `DESCRIBE TABLE EXTENDED ... AS JSON` (metric vs dimension; no Fact concept).
- Both engines already have offline mocked-connector unit tests
  (`tests/unit/test_snowflake_engine.py`, `tests/unit/test_databricks_engine.py`)
  that exercise `introspect()` with synthetic metadata rows.

The actual gap: **Snowflake and Databricks have no codegen E2E/snapshot test**
(only DuckDB does), and `_field_class_for` silently coerces unknown roles to
`Dimension`.

Out of scope: any new metadata-query design (the queries are already chosen and
coded); query-engine changes; live-warehouse integration tests.

</domain>

<decisions>
## Implementation Decisions

### No `Field()` fallback — every column resolves to a concrete role (locked)
- Every backend's metadata source returns a role for **every** column:
  - DuckDB `DESCRIBE SEMANTIC VIEW` → `object_kind` always DIMENSION/METRIC/FACT
  - Snowflake `SHOW COLUMNS IN VIEW` → `kind` always METRIC/DIMENSION/FACT
  - Databricks `is_measure` → metric, else dimension (binary, always resolves)
- Therefore the "unknown role" case **cannot occur**. Do NOT add a `Field()`
  placeholder path. (User: "There should be no unknown case, we have
  introspection for all backends.")
- **Criterion 4 must be rewritten** in ROADMAP.md/REQUIREMENTS.md from
  "Existing `Field()` fallback behaviour is preserved for columns whose role
  cannot be determined" → "every column resolves to a concrete role
  (`Metric`/`Dimension`/`Fact`) across all three backends; an unrecognized role
  string raises rather than silently defaulting."

### Strict `_field_class_for` — raise on unrecognized kind (locked)
- Change `python_renderer.py:_field_class_for()` from its current
  catch-all `return "Dimension"` to an **explicit** mapping:
  `"metric"` → `Metric`, `"fact"` → `Fact`, `"dimension"` → `Dimension`,
  **anything else → raise**.
- Rationale: "no unknown case" is now an enforced invariant. If a backend ever
  returns a `kind` we don't recognize (schema drift, new warehouse version), the
  generator must fail loudly instead of mislabeling the column as a Dimension and
  hiding the drift. (User chose strict over lenient.)
- Follows the project's bug-fix discipline: add a test asserting the raise path
  (unrecognized kind → error), adjacent to existing renderer tests.

### Snowflake + Databricks codegen tested OFFLINE via mocked metadata (locked)
- **No live warehouse access is available** (user's Snowflake trial expired) and
  none is needed. The established codebase pattern is offline mock-based
  introspection (`sys.modules` connector mocks already used in the engine unit
  tests).
- Add codegen E2E snapshot tests for Snowflake and Databricks that feed
  hand-crafted, realistic metadata rows through the mocked connector and snapshot
  the rendered Python — extending DuckDB's existing `test_codegen_e2e.py` pattern.
  - Snowflake fixture: synthetic `SHOW COLUMNS IN VIEW` rows with `kind` values
    METRIC / DIMENSION / FACT and JSON `data_type` payloads.
  - Databricks fixture: synthetic `DESCRIBE TABLE EXTENDED ... AS JSON` payload
    with `is_measure` true/false columns.
- This satisfies success criteria 2 & 3 ("verified against a snapshot fixture in
  the test suite") with zero warehouse dependency.

### Databricks has no Fact type (locked / documented constraint)
- Databricks metric views only support metric vs dimension. The "correct field
  type" for Databricks is metric/dimension only — there is no Fact. State this
  explicitly in the how-to and in the test's intent, so it doesn't read as a bug.

### DuckDB criterion 1 — verify, don't rebuild (locked)
- DuckDB inference + e2e snapshot already exist. The DuckDB work for this phase
  is confirming the existing snapshot still demonstrates per-role emission (and
  that it survives the strict-`_field_class_for` change), not new implementation.

### Close-out (locked)
- Amend the existing codegen how-to (not a new page) to document per-role
  field-type emission across all three backends + the Databricks no-Fact note +
  the strict-raise behaviour. Apply the semolina-docs-author skill.
- Close REQUIREMENTS.md DKGEN-05 traceability on phase close.
- Record in PROJECT.md Key Decisions: the per-backend metadata-query paths
  (`DESCRIBE SEMANTIC VIEW` / `SHOW COLUMNS IN VIEW` / `DESCRIBE TABLE EXTENDED
  AS JSON`) and the strict-raise-on-unrecognized-kind decision.

### Claude's Discretion
- Whether the SF/Databricks codegen e2e tests live in
  `tests/unit/codegen/test_codegen_e2e.py` or sibling files (planner decides per
  codebase conventions).
- Snapshot mechanism flavour (syrupy `.ambr` as DuckDB uses, vs golden module) —
  prefer matching the existing DuckDB e2e snapshot approach.
- Whether the synthetic metadata rows are authored fresh or lifted from the
  existing engine unit-test fixtures (planner should check reuse first — see
  planning note).
- Exact wording of the ROADMAP/REQUIREMENTS criterion-4 rewrite.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & Requirements
- `.planning/ROADMAP.md` — Phase 42 section is the authoritative scope/success-
  criteria contract. **Criterion 4 needs rewriting per the decision above.**
- `.planning/REQUIREMENTS.md` — DKGEN-05 definition + traceability table.

### Existing Implementation (must respect/verify — already built)
- `src/semolina/codegen/python_renderer.py` — `_field_class_for()` (~line 65–79)
  is the strict-raise target; `_FieldContext` / rendering context.
- `src/semolina/codegen/introspector.py` — `IntrospectedField.field_type`
  (the role string the renderer consumes).
- `src/semolina/codegen/templates/python_model.py.jinja2` — emits
  `{{ field.field_class }}[{{ field.data_type }}]()`; confirm no `Field()` import.
- `src/semolina/engines/duckdb.py` — `DESCRIBE SEMANTIC VIEW` parse (~line 39–63,
  145–287); already sets metric/dimension/fact.
- `src/semolina/engines/snowflake.py` — `introspect()` (~line 264–380);
  `SHOW COLUMNS IN VIEW`, `kind` at ~line 336.
- `src/semolina/engines/databricks.py` — `introspect()` (~line 271–375);
  `DESCRIBE TABLE EXTENDED ... AS JSON`, `is_measure` at ~line 336.
- `src/semolina/fields.py:668–698` — `Metric`/`Dimension`/`Fact` definitions
  (all subclass `Field[T]`).

### Existing Tests (extend these patterns — do NOT reinvent)
- `tests/unit/codegen/test_codegen_e2e.py` — DuckDB e2e codegen test to mirror
  for SF/Databricks.
- `tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr` — committed DuckDB
  snapshot (syrupy).
- `tests/unit/test_snowflake_engine.py` — `sys.modules` connector mock + synthetic
  `SHOW COLUMNS` introspection rows (reusable fixture source).
- `tests/unit/test_databricks_engine.py` — connector mock + `DESCRIBE TABLE
  EXTENDED AS JSON` introspection payload (reusable fixture source).
- `tests/unit/codegen/test_python_renderer.py` — adjacent home for the new
  strict-raise unit test.

### Prior Phases (consult, do NOT re-do)
- Phase 36 (DuckDB introspection baseline), Phase 41 (DuckDB file-backed codegen +
  e2e snapshot harness this phase mirrors).

### Project Standards
- `CLAUDE.md` — `prek run --all-files`, `just test`, `just docs-build`,
  line-length 100, no `# type: ignore`, **bug-fix-first-test-then-fix** rule.
- `.claude/skills/semolina-docs-author/SKILL.md` — MUST apply for the how-to
  amendment (Diataxis + humanizer); flag in any doc task `execution_context`.

</canonical_refs>

<specifics>
## Specific Ideas

- Strict mapping shape:
  ```python
  _ROLE_TO_CLASS = {"metric": "Metric", "dimension": "Dimension", "fact": "Fact"}
  def _field_class_for(field_type: str) -> str:
      try:
          return _ROLE_TO_CLASS[field_type]
      except KeyError:
          raise <SemolinaError>(f"Unrecognized field role: {field_type!r}") from None
  ```
  (Exact exception type is planner's discretion — prefer an existing Semolina
  error class over a bare `ValueError` if one fits.)
- Snowflake `kind` arrives uppercased and is `.lower()`-ed before reaching the
  renderer; Databricks maps `is_measure` → `"metric"`/`"dimension"`. The renderer
  only ever sees lowercase role strings — the strict map keys are lowercase.

</specifics>

<deferred>
## Deferred Ideas

None — phase scope is fully captured. (Cross-phase UAT audit of all of v0.5 is
already its own Phase 43.)

</deferred>

---

*Phase: 42-codegen-field-type-inference*
*Context gathered: 2026-06-09 via /gsd-discuss-phase --assumptions*
