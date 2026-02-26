---
phase: 18-fix-invalid-create-view-examples-in-first-query-tutorial
verified: 2026-02-23T17:30:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
gaps: []
human_verification: []
---

# Phase 18: Fix Invalid CREATE VIEW Examples Verification Report

**Phase Goal:** Fix invalid CREATE VIEW examples in first-query tutorial — replace invented Snowflake and Databricks DDL syntax with valid warehouse-native syntax matching official documentation.
**Verified:** 2026-02-23T17:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Snowflake DDL example uses valid CREATE SEMANTIC VIEW syntax with TABLES, DIMENSIONS, and METRICS clauses | VERIFIED | Lines 38-51 of first-query.md: `CREATE OR REPLACE SEMANTIC VIEW sales` with `TABLES (`, `DIMENSIONS (`, `METRICS (` all present and correctly ordered |
| 2 | Databricks DDL example uses valid CREATE VIEW ... WITH METRICS LANGUAGE YAML syntax with YAML body inside $$ delimiters | VERIFIED | Lines 56-73 of first-query.md: `CREATE OR REPLACE VIEW sales`, `WITH METRICS`, `LANGUAGE YAML`, `AS $$`, YAML body with `dimensions:` and `measures:` arrays, closing `$$;` |
| 3 | Neither DDL example uses query-time functions (AGG, MEASURE) in definitions | VERIFIED | Grep for `AGG\|MEASURE` in first-query.md returns no matches |
| 4 | Field names in DDL examples match the Cubano model fields (revenue, cost, country, region) | VERIFIED | Snowflake: `s.country AS country`, `s.region AS region`, `s.revenue AS SUM(revenue)`, `s.cost AS SUM(cost)`. Databricks: `name: country`, `name: region`, `name: revenue`, `name: cost` — all match model fields defined on lines 23-26 |
| 5 | MkDocs docs build passes with --strict flag | VERIFIED | `uv run mkdocs build --strict` exits with code 0, zero errors, zero warnings. Output: "Documentation built in 1.53 seconds" |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/src/tutorials/first-query.md` | Corrected DDL examples for both warehouse backends, containing `CREATE SEMANTIC VIEW` | VERIFIED | File exists, contains `CREATE OR REPLACE SEMANTIC VIEW` (line 38) and `CREATE OR REPLACE VIEW ... WITH METRICS LANGUAGE YAML` (lines 56-58). 282 lines total, substantive content throughout. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `docs/src/tutorials/first-query.md` | Snowflake official docs | Syntax matching `CREATE OR REPLACE SEMANTIC VIEW` reference | VERIFIED | `CREATE OR REPLACE SEMANTIC VIEW` present at line 38; TABLES clause (line 39), DIMENSIONS (line 42), METRICS (line 46) in correct mandatory order per official Snowflake DDL grammar |
| `docs/src/tutorials/first-query.md` | Databricks official docs | Syntax matching `CREATE VIEW ... WITH METRICS` reference | VERIFIED | `WITH METRICS` (line 57), `LANGUAGE YAML` (line 58), `AS $$` (line 59), YAML body with `version: 1.1`, `source:`, `dimensions:`, `measures:` — matches official Databricks YAML syntax reference |

### Requirements Coverage

No requirement IDs were declared for this phase (`requirements: []` in PLAN frontmatter). Phase is a docs-only fix with no functional requirements. Cross-reference against REQUIREMENTS.md is not applicable.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

No anti-patterns found. No TODO/FIXME/placeholder comments, no stub implementations, no query-time functions in DDL definitions.

### Human Verification Required

None. All must-haves are fully verifiable via static analysis and build output.

The only items a human might optionally confirm are:
- Visual rendering of the MkDocs tabbed blocks in a browser (the Markdown indentation is correct per verification, so rendering should follow)
- Whether a real Snowflake/Databricks engineer would recognize the DDL as idiomatic

These are not blockers — the syntax has been independently validated against official documentation in the RESEARCH.md phase.

### Gaps Summary

No gaps. All five must-have truths are fully verified:

1. The Snowflake DDL block (lines 38-51) uses the complete and correctly-ordered `CREATE OR REPLACE SEMANTIC VIEW` syntax: mandatory `TABLES` clause with `alias AS table PRIMARY KEY (col)` format, `DIMENSIONS` with `table_alias.name AS expr` format, and `METRICS` with `table_alias.name AS SUM(col)` format.

2. The Databricks DDL block (lines 56-73) uses `CREATE OR REPLACE VIEW ... WITH METRICS LANGUAGE YAML AS $$ ... $$` wrapping a YAML body with `version`, `source`, `dimensions`, and `measures` arrays.

3. Neither block contains `AGG()` or `MEASURE()` — the query-time functions that were incorrectly used in the original invented DDL.

4. Field names (`revenue`, `cost`, `country`, `region`) align between the Cubano model definition and both DDL examples.

5. `uv run mkdocs build --strict` exits with code 0 and emits no errors or warnings.

The commit `a01fe05` exists and documents the change: "fix(18-01): replace invalid DDL examples with correct warehouse syntax". The SUMMARY.md prose on line 33 was correctly updated from "maps to a view like:" to "maps to a definition like:" — a sensible adjustment since the Databricks block is YAML, not a SQL view.

---

_Verified: 2026-02-23T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
