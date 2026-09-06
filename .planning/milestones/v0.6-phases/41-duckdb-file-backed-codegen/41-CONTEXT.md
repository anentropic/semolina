# Phase 41: DuckDB File-Backed Codegen — Context

**Gathered:** 2026-05-15
**Status:** Ready for planning
**Source:** Captured from `/gsd-list-phase-assumptions 41` discussion (assumptions surfaced + validated)

<domain>
## Phase Boundary

Codegen against an on-disk DuckDB `.db` file. The DuckDB engine already accepts a
`database=` path and the CLI already exposes `--database`; this phase **fills the
gaps** rather than building greenfield:

1. Path handling at the CLI boundary (`~` expansion, relative→absolute, but **not**
   for the `:memory:` sentinel).
2. Codegen-time auto-install of the `semantic_views` extension on the native
   (non-ADBC) DuckDB connection used by introspection.
3. A pytest-generated `.db` fixture + end-to-end codegen test against it.
4. Packaging smoke test confirming the `[duckdb]` extra still installs cleanly.
5. Documentation amendment (existing how-to) + REQUIREMENTS.md DKGEN-04 traceability.

Out of scope: field-type inference (Phase 42), query execution against file-backed
DuckDB, ADBC connection paths, new how-to pages.

</domain>

<decisions>
## Implementation Decisions

### Path Handling (locked)
- **Apply `expanduser()` + `resolve(strict=False)`** to the `--database` value AND
  to the value of the `DUCKDB_DATABASE` env-var fallback. Same treatment for both
  sources (user confirmed).
- **Skip expansion for the `:memory:` sentinel.** Guard pattern:
  ```python
  if database and database != ":memory:":
      database = str(Path(database).expanduser().resolve(strict=False))
  ```
  This protects the default codegen behavior — `Path(":memory:").resolve()` would
  rewrite the sentinel into a cwd-relative filename and DuckDB would try to open
  it as a real file (user confirmed: "yes definitely this").
- Use `resolve(strict=False)` (not strict). Let DuckDB itself raise the
  file-not-found error so the error path is consistent with other
  database-open failures.

### Extension Install at Codegen Time (locked)
- `INSTALL semantic_views FROM community; LOAD semantic_views` must run on the
  **native** DuckDB connection used by introspection (the non-ADBC connection at
  `src/semolina/engines/duckdb.py:198`). Currently only `LOAD` is called there.
- INSTALL is idempotent (caches at `~/.duckdb/extensions/`). Mirrors the existing
  ADBC-side hook in `src/semolina/config.py:40`.

### Fixture Strategy (locked — user-confirmed)
- **pytest fixture generates the `.db` at test-collection time.** Do NOT commit a
  binary `.db` blob — user preference is explicit:
  > "fine with generate it from scratch in a pytest fixture or whatever, prefer
  > that to committing the blob"
- The fixture script becomes the authoritative spec for what the test DB
  contains; no opaque binary diffs in git history.
- Pin DuckDB version via the existing `[duckdb]` extra to keep fixture-generation
  deterministic across machines.

### End-to-End Codegen Test (locked)
- Drive the CLI surface (`semolina codegen --backend duckdb --database <fixture>`),
  not just internal APIs — the success criterion specifies "generates the same
  model classes as the in-memory equivalent."
- Assert against generated module output. Prefer a regenerate-on-flag pattern
  (`UPDATE_SNAPSHOTS=1` or equivalent) over brittle string-for-string compares
  so Phase 42's field-type changes don't fight this test unnecessarily.

### Packaging Smoke Test (locked)
- CI verifies `uv pip install '.[duckdb]'` in a clean environment + an import
  smoke test for `semolina.engines.duckdb`. Narrow scope — no functional
  assertions. Carries forward the v0.4.0 Phase 38 lesson.

### Documentation (locked)
- **Amend** the existing DuckDB codegen how-to (not a new page) — explicitly
  required by success criterion #5.
- Update REQUIREMENTS.md DKGEN-04 traceability on close.

### Claude's Discretion
- File layout for the pytest fixture (probably `tests/fixtures/` and/or
  `conftest.py` — planner decides).
- Snapshot-mechanism flavor (raw file comparison vs `syrupy` vs manual fixture
  golden module — planner decides; codebase conventions take precedence).
- Exact CI workflow file/job placement for the `[duckdb]` extras smoke test.
- Whether path-normalization helper lives in `cli/codegen.py` or `cli/utils.py`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & Requirements
- `.planning/ROADMAP.md` — Phase 41 section (lines 129-139) is the authoritative
  scope/success-criteria contract
- `.planning/REQUIREMENTS.md` — DKGEN-04 definition + traceability table

### Existing Implementation (must respect/extend these)
- `src/semolina/engines/duckdb.py` — DuckDBEngine; `database` param already
  accepts file paths (line 96); INSTALL hook target is line 198–199
- `src/semolina/cli/codegen.py` — `_resolve_backend` at line 28; `--database`
  CLI option at line 104; env-var fallback at line 109
- `src/semolina/config.py:30-41` — `_load_semantic_views` ADBC-side hook;
  template for the codegen-side install pattern
- `src/semolina/codegen/introspector.py` — IR consumed by the renderer
- `src/semolina/codegen/python_renderer.py` — emits the generated module

### Prior Phases (consult, do NOT re-do)
- Phase 36 (DuckDB introspection engine baseline)
- Phase 38 (v0.4.0 in-memory DuckDB codegen; packaging-smoke lesson learned)

### Project Standards
- `CLAUDE.md` — `prek run --all-files`, `just test`, line-length 100,
  bug-fix-first-test-then-fix rule
- `.claude/skills/semolina-docs-author/SKILL.md` — MUST apply for any docs work
  (Diataxis + humanizer pass); flagged in any doc tasks' `execution_context`

</canonical_refs>

<specifics>
## Specific Ideas

- The `:memory:` guard is the single most important detail — easy to break
  silently. Add a unit test asserting `_resolve_backend("duckdb", database=":memory:")`
  leaves the sentinel unchanged.
- INSTALL FROM community requires network access on first run only (then
  extension is cached under `~/.duckdb/extensions/`). CI may need a cache-warming
  step or to accept first-run network. Worth a marker like `@pytest.mark.requires_network`
  or a session-scoped cache fixture if test isolation needs it.
- Error messaging: when `--database` points at a non-existent file, let DuckDB's
  native error bubble (wrapped in `SemolinaConnectionError` at
  `src/semolina/engines/duckdb.py:174`). Do not pre-validate file existence in
  the CLI — duplicates work and creates two error paths.
- The how-to amendment should at minimum cover: `--database <path>` usage,
  relative + `~` expansion behavior, that `:memory:` is still the default,
  and a brief note on the auto-installed `semantic_views` extension.

</specifics>

<deferred>
## Deferred Ideas

- Field-type inference across backends — explicitly Phase 42.
- Query execution against file-backed DuckDB — DuckDBEngine is introspection-only
  by design; not changing in this phase.
- ADBC connection support for file-backed DuckDB — out of scope (criterion #2
  specifies non-ADBC connection only).
- A new dedicated "DuckDB file-backed codegen" how-to page — explicitly an
  amendment of the existing how-to per criterion #5.

</deferred>

---

*Phase: 41-duckdb-file-backed-codegen*
*Context gathered: 2026-05-15 via `/gsd-list-phase-assumptions` interactive validation*
