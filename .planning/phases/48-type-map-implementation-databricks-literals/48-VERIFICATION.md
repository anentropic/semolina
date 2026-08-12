---
phase: 48-type-map-implementation-databricks-literals
verified: 2026-08-12T15:46:11Z
status: human_needed
score: 5/6 truths verified
behavior_unverified: 0
overrides_applied: 0
gaps: []
human_verification:
  - test: "Decide whether the unmapped Databricks `interval` half of TYPE-05 is acceptable to ship as-is (add a VERIFICATION.md override) or should be tracked as a blocking gap for a future phase."
    expected: "Either (a) a developer adds an `overrides:` entry accepting the documented evidence-blocked revert, or (b) the team decides TYPE-05 stays open and schedules the Databricks-workspace recording session (`.planning/todos/pending/2026-08-12-record-databricks-interval-column.md`) before treating Phase 48 as fully closing its own roadmap Success Criterion 3."
    why_human: "This is a genuine, roadmap-explicit unmet criterion (SC3 names 'Databricks interval' as a type that must stop emitting a `TODO:`), but the shortfall is not an execution defect — it is a deliberate, well-reasoned reversal the user directed mid-session (recorded verbatim in 48-03-SUMMARY.md as 'Directed by the user through the coordinator, mid-plan') because no fixture, cassette, or recording anywhere in the repo lets the annotation be measured. Whether this counts as 'phase goal achieved with a documented, accepted limitation' or 'phase goal not yet achieved' is a product/scope call, not something resolvable by re-reading code."
---

# Phase 48: Type Map Implementation & Databricks Literals — Verification Report

**Phase Goal:** Generated models carry the types the decision doc specifies, identically
across Snowflake, Databricks, and DuckDB, and Databricks filters accept the value types that
policy now makes reachable.
**Verified:** 2026-08-12T15:46:11Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Verification method

This is not a re-statement of the six SUMMARY.md files. Every claim below was checked against
the current working tree: `type_map.py`, `python_renderer.py`, `sql.py`, `probe.py`,
`arrow_map.py`, `model_reader.py`, `annotation_check.py`, `cli/codegen.py`, `types.py`, and
`__init__.py` were read directly; the full relevant test surface (621 tests across
`tests/unit/codegen`, `tests/unit/test_sql.py`, `tests/unit/test_type_fidelity_*`,
`tests/unit/test_annotation_contract.py`, `tests/unit/test_public_surface.py`,
`tests/unit/test_scope_fence.py`) was executed live (619 passed, 2 xfailed); `just docs-build`
and `prek run --all-files` were run live and both came back clean; the scope-fence gate was run
live with `SEMOLINA_SCOPE_FENCE_BASE=9f3c8b9` (1 passed, not skipped); the git-diff prohibition
gates (`cursor.py`/`acursor.py`/`results.py`/`47-DECISIONS.md` untouched) were re-run
independently of the summaries' claims; and several of the `48-VALIDATION.md` per-requirement
`-k` selector commands were re-run verbatim to confirm they actually collect and pass what they
claim (see Anti-Patterns / Findings — one more misfired selector was found, undetected by 48-06's
own correction pass).

## Goal Achievement

### Observable Truths

| # | Truth (roadmap Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | SC1/TYPE-03: An equivalent decimal column annotates `decimal.Decimal` identically on Snowflake, Databricks, DuckDB | VERIFIED | `type_map.py` — `FIXED`→`decimal.Decimal` (no scale branch), `"decimal"`→`decimal.Decimal`, `DECIMAL`→`decimal.Decimal`, `HUGEINT`→`decimal.Decimal` (D-05). Live: `test_type_map.py` 161/161 pass; `.ambr` snapshot for `test_codegen_snowflake_field_types` shows `Metric[decimal.Decimal \| None]()`; `test_annotation_contract.py` proves it against measured values on all three backends |
| 2 | SC2/TYPE-04: Metric annotations get `T \| None`; dimensions/facts do not | VERIFIED | `python_renderer.py::metric_annotation` applies `\| None` only when `field_class == "Metric"`; live check: constructing a metric field yields `Metric[...\| None]()`, a dimension field yields `Dimension[str]()` with no `\| None` (reproduced directly, see below); `test_python_renderer.py` 55/55 pass, `-k import` pitfall-1 guard 14/14 pass |
| 3a | SC3/TYPE-05 (DuckDB half): DuckDB `DECIMAL`/`UUID`/`JSON`/`ENUM`/`TIMESTAMP_S\|_MS\|_NS` get a concrete type, not `TODO:` | VERIFIED | `_DUCKDB_TYPE_MAP` carries all listed keys mapped to measured types (D-03 table honored exactly: `UUID`→`str`, `JSON`→`str`, `ENUM`→`str`, `TIMESTAMP_S/_MS/_NS`→`datetime.datetime`); `test_annotation_contract.py::test_duckdb_annotation_describes_the_measured_value` proves each by `isinstance` against a live DuckDB value (10 columns, live in-memory engine, re-run and green) |
| 3b | SC3/TYPE-05 (Databricks interval half): Databricks `interval` gets a concrete type, not `TODO:` | **NOT MET — deliberate, evidence-blocked** | `databricks_type_to_python` has no `interval` branch (confirmed by reading the function); both interval families return `None` and still emit `TODO:` (`TestDatabricksIntervalType`, 6/6 pass, asserting the refusal). REQUIREMENTS.md correctly keeps TYPE-05 **Pending** (not `[x]`); WINDOWS.md entry 7 (`unrun-verify`, open) and a pending todo track it. See Human Verification below — this is the phase's own documented headline gap, not something this verifier discovered |
| 4 | SC3/TYPE-06: VARIANT columns get `JsonValue`, not `Any` | VERIFIED | `semolina.JsonValue` importable from package root, in `__all__` (confirmed live: `'JsonValue' in semolina.__all__` → `True`); `VARIANT`/`variant` map to `"JsonValue"` in both maps; `test_public_surface.py` 4/4 pass, `test_type_map.py -k variant` 2/2 pass (run separately — see Findings for a validation-doc inaccuracy in the compound command). The mapping's *value-level* correctness is an accepted evidence limit (WINDOWS.md entry 8, open) — no VARIANT fixture exists to `isinstance`-check it — but this was explicitly evaluated and accepted (a `JsonValue` union holds under both plausible outcomes), unlike the interval case, and REQUIREMENTS.md correctly marks TYPE-06 Complete |
| 5 | SC4/TYPE-07: `--check` reports annotation drift against the warehouse's current result schema, fetching no rows | VERIFIED | Live, in-process: `semolina codegen --help` shows the `--check`/`--model` flags and exit code 5; `EXIT_ANNOTATION_DRIFT == 5` confirmed live; `test_cli.py -k check` 44/44 pass (incl. live-DuckDB drift/no-drift, no-data-fetch, route reporting); Snowflake comparison core proven against the real recorded Arrow schema. Databricks `--check` is explicitly and correctly out of scope by decision D-09 (no acceptance criterion written, none claimed) — this is documented, not silently dropped (WINDOWS.md entries 2 and 9, both open) |
| 6 | SC5/DBX-04: Databricks `.where()` on `date`/`datetime`/`Decimal` inlines correctly instead of raising `NotImplementedError` | VERIFIED | Read `render_literal` in both `Dialect` and `DatabricksDialect` directly — three new branches each, `datetime` tested before `date` (subclass-order comment present), Decimal via `format(value, "f")` (no `CAST`, no exponent), aware datetime normalised to UTC `Z` (D-08, `_timestamp_literal_text`); `test_sql.py -k RenderLiteralDatabricks` 20/20 pass, `-k DatabricksLiteralInlining` 6/6 pass, `-k non_finite` 4/4 pass. Live-warehouse acceptance is unverified (WINDOWS.md entry 5, open, `unrun-verify`) — an accepted, documented evidence limit consistent with Phase 47's own established pattern for exactly this kind of claim, not a code defect |

**Score:** 5/6 truths verified (one truth, 3b, is explicitly and honestly NOT met — see Human
Verification). No truth is a silent gap: every unmet or evidence-limited item above is recorded
in WINDOWS.md, in a pending todo, and/or in REQUIREMENTS.md's own Pending/Complete columns,
which this verifier independently confirmed match the code.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/semolina/codegen/type_map.py` | Decimal/D-03/D-05/D-06/TYPE-06 keys | VERIFIED | Read in full; matches every claim above byte-for-byte |
| `src/semolina/codegen/python_renderer.py` | Nullability seam, import emission, raw-type comment | VERIFIED | `metric_annotation`, `_build_import_lines`, `type_comment` all present and exercised live |
| `src/semolina/codegen/templates/python_model.py.jinja2` | `import_lines` block | VERIFIED | `needs_datetime`/`needs_any` absent (`grep` confirms), `import_lines` present |
| `src/semolina/codegen/introspector.py` | `IntrospectedField.raw_type` | VERIFIED | Field present, populated at all three engine call sites (`raw_type=` appears once per engine file) |
| `src/semolina/types.py` | `JsonValue` | VERIFIED | Present, exported, subscriptable, live-imported |
| `src/semolina/codegen/probe.py` | Shipped `probe_schema`/`ProbeResult` | VERIFIED | Exists in `src/`; does not import `type_map` (AST-guard test passes) |
| `src/semolina/codegen/arrow_map.py` | `arrow_type_to_python` | VERIFIED | Exists, predicate-based (no `str(dtype)` call in the executable body); 62 tests pass |
| `src/semolina/codegen/model_reader.py` | AST-only model reader | VERIFIED | Exists; `ast.parse` only, no `import_module`/`exec` in the module |
| `src/semolina/codegen/annotation_check.py` | `check_view`, `ViewCheckReport` | VERIFIED | Exists, drives `--check`'s comparison core, 18 tests pass |
| `src/semolina/engines/sql.py` | Widened `render_literal` × 2 | VERIFIED | Both dialects widened identically in shape, per D-07 |
| `tests/unit/test_scope_fence.py` | Runnable prohibition gate | VERIFIED | Exists, passes non-vacuously with the base ref set explicitly; also proven to skip loudly (not pass) when the ref is unresolvable (per 48-01 summary, not independently re-proven here since it would require detaching from the real ref) |
| `.planning/phases/47-type-fidelity-probe-decision-doc/47-TYPE-FIDELITY.md` | Regenerated, byte-stable | VERIFIED | `uv run python tests/type_fidelity_probe.py --check` exits 0 live |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `type_map.py` mappers | `python_renderer._build_model_context` | resolved `data_type` string | WIRED | `\| None` applied only at the renderer seam; no map or engine contains `\| None` (confirmed: only the 3 `-> str \| None` return-type annotations match a bare grep, all pre-existing, none are map values) |
| `IntrospectedField.raw_type` (3 engines) | renderer `type_comment` | `_RAW_TYPE_COMMENT_*` frozensets | WIRED | Live repro above shows `# DECIMAL(38,2)` comment emitted for a lossy annotation and no comment for a non-lossy one |
| `annotation_check.check_view` | `probe.probe_schema` + `engine.introspect` | two-route merge, labelled | WIRED | Live `--check` run against DuckDB reports `execute-schema` route on every field in this repo's fixtures; `span_view`'s `INTERVAL` fact is the live test proving the metadata-vs-probe divergence D-02 accepts is actually surfaced, not suppressed |
| `codegen` generation path | `engine.introspect` (metadata only) | unchanged | WIRED, and confirmed NOT probe-primary | `grep` for `probe_schema`/`arrow_type_to_python`/`codegen.probe`/`codegen.arrow_map` across all three engine files returns nothing — D-01's prohibition against making generation probe-primary is honored |
| `Dialect.render_literal` (base) | `SQLBuilder._render_literal_sql` | generic caller, no per-type branching | WIRED | `_render_literal_sql` unmodified; both dialects reached the same way as before |

### Prohibitions (must-NOT checks)

| Prohibition | Status | Evidence |
|---|---|---|
| `src/semolina/cursor.py`/`acursor.py`/`results.py` untouched | VERIFIED | `git diff --name-only 9f3c8b9..HEAD` naming any of the three: empty, re-run independently |
| `.planning/phases/47-.../47-DECISIONS.md` untouched | VERIFIED | `git diff --name-only 9f3c8b9..HEAD` naming it: empty, re-run independently |
| No `# type: ignore` added by Phase 48 | VERIFIED (per 48-06's count, spot-checked plausible) | Pre-phase/post-phase count both 32 per 48-06; not independently recounted here but the five new modules were read in full and contain none |
| Generation path stays metadata-only (D-01) | VERIFIED | See key-link row above; independently confirmed by grep, not just by summary claim |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `.planning/phases/48-.../48-VALIDATION.md` | TYPE-06 row | A "corrected" test-selector command that still does not execute what it claims when run verbatim | ℹ️ Info (documentation accuracy only) | `uv run pytest tests/unit/codegen/test_type_map.py -k variant tests/unit/test_public_surface.py -x` — as literally written, `-k variant` filters **both** file arguments, and none of `test_public_surface.py`'s 4 tests contain "variant" in their name. Running the exact command yields `2 passed, 163 deselected` (verified live), not "2 + 4 pass" as the row claims. 48-06's own correction pass fixed this row's *file path* (from the wrong `test_models.py`) but did not notice the compound command still deselects the second file's tests. This is the sixth instance of the "misfired `-k`/grep criterion" pattern this phase's own summaries flagged five times already (48-01, 48-03 ×2, 48-04, 48-05) — the underlying functionality is fine (both halves pass when run as two separate commands, confirmed live), but the validation artifact itself still slightly overstates what one copy-pasted command proves. Not a code or test gap; a residual accuracy issue in `48-VALIDATION.md` worth a follow-up edit. |
| — | — | No `TBD`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` markers | — | Scanned all 15 phase-modified/created `src/` files directly; zero hits |

No blocker-severity anti-patterns found. No stub implementations, no orphaned artifacts, no
disconnected data flow.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| TYPE-03 | 48-01, 48-03 | Decimal type consistent across all 3 backends | SATISFIED | See truth 1 |
| TYPE-04 | 48-01 | Metric nullability | SATISFIED | See truth 2 |
| TYPE-05 | 48-01, 48-03 | Category-1 map gaps (DuckDB + Databricks interval) | **PARTIALLY SATISFIED — by decision** | See truths 3a (met) / 3b (not met, evidence-blocked). REQUIREMENTS.md correctly shows this as `Pending`, matching the code — not an unreported gap |
| TYPE-06 | 48-03 | VARIANT → JsonValue | SATISFIED | See truth 4 |
| TYPE-07 | 48-04, 48-05 | `--check` drift mode | SATISFIED (DuckDB live + Snowflake comparison core; Databricks explicitly out of scope) | See truth 5 |
| DBX-04 | 48-02 | Databricks literal widening | SATISFIED (code + tests; live-warehouse acceptance unverified, tracked) | See truth 6 |

No orphaned requirements: all six IDs declared in `.planning/REQUIREMENTS.md` for Phase 48
appear in at least one plan's `requirements:` frontmatter, and every plan's declared
requirements map to a roadmap ID.

### Behavioral Spot-Checks (live, run by this verifier)

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full phase-relevant test surface | `uv run pytest tests/unit/codegen tests/unit/test_sql.py tests/unit/test_type_fidelity_duckdb.py tests/unit/test_type_fidelity_table.py tests/unit/test_annotation_contract.py tests/unit/test_public_surface.py tests/unit/test_scope_fence.py -q` | 619 passed, 2 xfailed, 3 snapshots passed | ✓ PASS |
| Scope fence, base set explicitly | `SEMOLINA_SCOPE_FENCE_BASE=9f3c8b9 uv run pytest tests/unit/test_scope_fence.py -x -v` | 1 passed | ✓ PASS |
| Type-fidelity artifact staleness | `uv run python tests/type_fidelity_probe.py --check` | exit 0 | ✓ PASS |
| Docs build, strict | `just docs-build` | build succeeded | ✓ PASS |
| Lint/format/typecheck | `prek run --all-files` | all hooks passed | ✓ PASS |
| Nullability + comment channel, live repro | `render_views([...])` with a metric+dimension pair | `# DECIMAL(38,2)` comment, `Metric[decimal.Decimal \| None]()`, `Dimension[str]()` with no `\| None` | ✓ PASS |
| `JsonValue` public surface, live repro | `'JsonValue' in semolina.__all__`, `semolina.JsonValue` | `True`, resolves to the recursive union | ✓ PASS |
| CLI exit-code surface, live repro | `uv run semolina codegen --help`; `EXIT_ANNOTATION_DRIFT` | `5` row present with "Annotation drift" text; constant equals `5` | ✓ PASS |
| Exit-code doc/code duplication | `grep -n "Annotation drift" src/semolina/cli/__init__.py docs/src/how-to/codegen.rst` | Byte-identical wording in both | ✓ PASS |
| Prohibition gates, re-run independently | `git diff --name-only 9f3c8b9..HEAD \| grep -E '(cursor\|acursor\|results)\.py'` and `\|47-DECISIONS.md` | both empty | ✓ PASS |
| `-k` selector spot-checks (7 of the 18 `48-VALIDATION.md` rows) | see Findings | 6 of 7 match exactly; 1 (TYPE-06 compound) does not match as literally written | ⚠ MOSTLY PASS |

### Probe Execution

Not applicable — this phase's "probe" (`tests/type_fidelity_probe.py --check`) was exercised
directly above under Behavioral Spot-Checks; there is no separate `scripts/*/tests/probe-*.sh`
convention in this repository.

## Human Verification Required

### 1. Accept or escalate the unmapped Databricks `interval` (TYPE-05)

**Test:** Review whether shipping Phase 48 with Databricks `interval` still emitting `TODO:`
is acceptable as a documented limitation, or whether it should block phase closure until the
recording session in `.planning/todos/pending/2026-08-12-record-databricks-interval-column.md`
happens.

**Expected:** A developer decision, recorded either as (a) an `overrides:` entry in this
VERIFICATION.md's frontmatter accepting the deviation (suggested text below), or (b) an explicit
statement that TYPE-05 stays open pending the recording session, with the milestone/roadmap
adjusted accordingly.

**Why human:** This is not a code defect to fix — `databricks_type_to_python` correctly refuses
to guess, and the refusal is fully tested. It is a scope question: the roadmap's own SC3 wording
names "Databricks interval" as something that must get a concrete type, and it does not. The
user already directed this exact reversal mid-execution (48-03-SUMMARY.md), so the "right"
technical answer is already settled; what remains is whether that settlement should read as
"Phase 48 done, with a tracked limitation" or "Phase 48 not fully done, blocked on external data
this repo cannot produce." Both are defensible; only the person accountable for the roadmap can
pick.

**Suggested override, if accepted:**

```yaml
overrides:
  - must_have: "Databricks interval gets a concrete Python type instead of a TODO placeholder (roadmap SC3 / TYPE-05)"
    reason: "No fixture, cassette, or recording anywhere in the repo contains a Databricks interval column, so the annotation cannot be measured. A day-time datetime.timedelta guess was implemented in 48-02 and reverted in 48-03 per the user's own mid-session directive to measure rather than guess. Tracked as WINDOWS.md broken window 7 and .planning/todos/pending/2026-08-12-record-databricks-interval-column.md; REQUIREMENTS.md correctly keeps TYPE-05 Pending rather than Complete."
    accepted_by: "{your name}"
    accepted_at: "{ISO timestamp}"
```

## Gaps Summary

There is no execution-quality gap in this phase. Every artifact this verifier checked exists,
is substantive, is wired, and behaves as claimed when exercised live — including cases the
phase's own summaries flagged as previously-misfired acceptance criteria, which were spot-checked
and (with the one exception above) confirmed corrected. The full automated suite, lint/typecheck,
docs build, and the git-diff prohibition gates all pass cleanly right now, not merely "as of the
last commit."

The one open item is a scope question the phase's own artifacts already surface honestly:
Databricks `interval` (part of TYPE-05 / roadmap SC3) is not mapped, by a deliberate,
well-evidenced, user-directed decision that could not be resolved without external data
(a live Databricks workspace or a recording of one). REQUIREMENTS.md, WINDOWS.md, and a pending
todo all already reflect this truthfully — nothing was hidden or glossed over. This verifier is
surfacing it as a `human_needed` item rather than either silently passing it (which would
misrepresent the roadmap's literal wording) or failing the phase outright (which would demand
a repair this phase cannot perform without infrastructure nobody here has access to).

A secondary, much smaller finding: `48-VALIDATION.md`'s TYPE-06 requirement-row command does not
execute as literally written (see Anti-Patterns) — a documentation-accuracy issue, not a
functional one, since both halves of the claim pass when run as separate commands (independently
verified).

---

*Verified: 2026-08-12T15:46:11Z*
*Verifier: Claude (gsd-verifier)*
