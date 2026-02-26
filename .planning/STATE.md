# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-26)

**Core value:** A single, Pythonic query API that works identically across Snowflake and Databricks semantic views, with typed models, IDE autocomplete, and backend-agnostic code.
**Current focus:** Planning next milestone (v0.3)

## Current Position

Milestone: v0.2 COMPLETE — shipped 2026-02-26
Phase: All 20 phases (8-24) complete
Status: v0.2 archived. ROADMAP.md reorganized, REQUIREMENTS.md deleted, PROJECT.md evolved, git tagged v0.2.
Last activity: 2026-02-26 — Quick task 11.1 verified: fix CI test failures (ANSI suppression via _TYPER_FORCE_DISABLE_TERMINAL in pytest_configure)

Progress: [████████████████████] 100% (Phase 20.1: 5 of 5 plans)
Phase 20.1: 5 of 5 plans complete

## Performance Metrics

**Velocity (v0.1 completed):**
- Total plans completed: 18
- Average duration: 3.62 min
- Total execution time: 1.09 hours

**v0.2 Progress:**
- Phase 8: 6 of 6 plans complete (Integration Testing) ✅
- Phase 9: 4 of 4 plans complete (Codegen CLI) ✅
- Phase 10: 4 of 4 plans complete (Documentation) ✅
- Phase 10.1: 8 of 8 plans complete (Query Interface Refactor) ✅
- Phase 11: 2 of 2 plans complete (CI & Example Updates) ✅
- Phase 12: 4 of 4 plans complete (Warehouse Testing Syrupy) ✅
- Total v0.2: 28 of 28 plans

**By Phase (v0.1 archive):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-model-foundation | 1 | 3min | 3min |
| 02-query-builder | 3 | 11.08min | 3.69min |
| 03-sql-generation-mock-backend | 5 | 46min | 9.2min |
| 04-execution-results | 3 | 8min | 2.67min |
| 05-snowflake-backend | 2 | 7.78min | 3.89min |
| 06-databricks-backend | 2 | 9min | 4.5min |
| 07-packaging | 3 | 8.07min | 2.69min |

*Updated after v0.2 roadmap creation*
| Phase 08 P01 | 3.08 | 3 tasks | 5 files |
| Phase 08 P03 | 4.85 | 3 tasks | 5 files |
| Phase 08 P02 | 146 | 3 tasks | 2 files |
| Phase 08 P04 | 3 | 3 tasks | 4 files |
| Phase 08 P04 | 3 | 3 tasks | 4 files |
| Phase 08 P05 | 1 | 1 task | 1 file |
| Phase 08 P06 | 2 | 1 task | 2 files |
| Phase 09 P01 | 10 | 8 tasks | 9 files |
| Phase 09 P02 | 3 | 5 tasks | 6 files |
| Phase 09 P03 | 6 | 6 tasks | 5 files |
| Phase 09 P04 | 6 | 8 tasks | 10 files |
| Phase 10 P02 | 4 | 2 tasks | 8 files |
| Phase 10 P01 | 2 | 3 tasks | 16 files |
| Phase 10 P03 | 4 | 2 tasks | 10 files |
| Phase 10 P04 | 2 | 2 tasks | 3 files |
| Phase 10.1 P01 | 2.08 | 3 tasks | 3 files |
| Phase 10.1 P02 | 3.45 | 2 tasks | 3 files |
| Phase 10.1 P05 | 8.5 | 2 tasks | 4 files |
| Phase 10.1 P07 | 7 | 4 tasks | 24 files |
| Phase 10.1 P08 | 1.5 | 4 tasks | 0 files |
| Phase 11 P01 | 8 | 2 tasks | 1 file |
| Phase 11 P02 | 15 | 4 tasks | 3 files |
| Phase 12 P01 | 4 | 2 tasks | 3 files |
| Phase 12 P02 | 3 | 2 tasks | 2 files |
| Phase 12 P03 | 1 | 1 task | 1 file |
| Phase 12 P04 | 2 | 2 tasks | 2 files |
| Phase 10.1 P04 | 2 | 2 tasks | 3 files |
| Phase 10.1-refactor-query-interface-to-model-centric P03 | 2 | 1 tasks | 1 files |
| Phase 13 P02 | 2 | 2 tasks | 2 files |
| Phase 13 P03 | 2 | 1 tasks | 1 files |
| Phase 13 P04 | 2 | 2 tasks | 1 files |
| Phase 13.1 P01 | 3 | 1 task (TDD) | 3 files |
| Phase 13.1 P02 | 3 | 1 task (TDD) | 2 files |
| Phase 13.1 P03 | 6 | 1 task (TDD) | 4 files |
| Phase 13.1 P04 | 9 | 3 tasks | 12 files |
| Phase 13.1 P05 | 7 | 2 tasks | 8 files |
| Phase 14 P01 | 5 | 2 tasks | 17 files |
| Phase 14 P02 | 3 | 2 tasks | 6 files |
| Phase 14 P03 | 6 | 2 tasks | 10 files |
| Phase 14 P05 | 4 | 2 tasks | 7 files |
| Phase 14 P04 | 5 | 2 tasks | 8 files |
| Phase 15 P01 | 1 | 1 task | 1 file |
| Phase 15 P03 | 1 | 1 tasks | 2 files |
| Phase 15 P02 | 2 | 1 tasks | 3 files |
| Phase 16 P01 | 2 | 2 tasks | 2 files |
| Phase 17 P01 | 5 | 2 tasks | 8 files |
| Phase 18 P01 | 1 | 1 task | 1 file |
| Phase 19 P01 | 2 | 1 task | 2 files |
| Phase 19 P01 | 2 | 1 tasks | 2 files |
| Phase 20 P02 | 5 | 3 tasks | 4 files |
| Phase 20 P03 | 4 | 3 tasks (TDD) | 3 files |
| Phase 20 P04 | 4 | 3 tasks | 15 files |
| Phase 20 P05 | 2 | 2 tasks | 9 files |
| Phase 20.1 P01 | 7 | 3 tasks | 5 files |
| Phase 20.1 P02 | 7 | 2 tasks | 10 files |
| Phase 20.1 P03 | 4 | 2 tasks | 9 files |
| Phase 20.1 P04 | 4 | 2 tasks | 5 files |
| Phase 20.1 P05 | 13 | 1 tasks | 1 files |
| Phase 21 P01 | 12 | 3 tasks | 4 files |
| Phase 22 P01 | 1 | 1 tasks | 1 files |
| Phase 23 P01 | 2 | 4 tasks | 3 files |
| Phase 24 P03 | 2 | 2 tasks | 13 files |
| Phase 24-v02-tech-debt-cleanup P01 | 3.9 | 3 tasks | 3 files |
| Phase 24-v02-tech-debt-cleanup P02 | 5 | 3 tasks | 3 files |
| Phase 24-v02-tech-debt-cleanup P04 | 5 | 2 tasks | 2 files |

## Accumulated Context

### Decisions

Key v0.2 decisions from research and context gathering:

- **Phase 8 (Integration Tests):** Smart credential loader (env → .env → config → prompt), mixed test suite (mock + real), real warehouse tests opt-in locally, mock tests for logic + real tests for edge cases and SQL validation
- **Phase 9 (Codegen):** Jinja2 templates (maintainable, human-readable), Typer CLI (maintainable, battle-tested), separate package from core (maintain zero-dependency principle)
- **Phase 10 (Documentation):** MkDocs over Sphinx (simpler for 28-item API), Material theme (mobile responsive), doctest validation in CI (prevent stale examples)
- [Phase 10-04]: Two-job pattern (build artifact then deploy) avoids `contents: write` — only `pages: write` and `id-token: write` required for deploy-pages action
- [Phase 10-04]: Doctest items from src/ have no markers — they run unconditionally alongside marker-filtered tests when src/ is added to pytest command
- **Dependency order:** Phase 8 first (validates v0.1 stability), Phase 9 second (independent), Phase 10 third (references both)

All v0.1 decisions documented in v0.1-ROADMAP.md archive.
- [Phase 08]: Mock tests validate query API usage without warehouse connections, providing < 1 second feedback
- [Phase 08]: Session-scoped warehouse fixtures with per-worker schema isolation for parallel-safe integration testing
- [Phase 08]: Use @pytest.mark.warehouse for selective integration test execution
- [Phase 08]: Test result structure and behavior, not exact values (data varies across environments)
- [Phase 08-05]: CUBANO_ENV_FILE env var > env_file parameter > .env default is the priority chain for credential loaders
- [Phase 08-05]: Use _env_file at cls() instantiation (not model_config) for runtime env_file override in pydantic-settings
- [Phase 08-06]: Use monkeypatch.chdir() + per-test env var deletion to fully isolate credential loading in unit tests
- [Phase 09-01]: Register codegen as app.command("codegen") directly rather than add_typer() to avoid double-nesting (cubano codegen <input> not cubano codegen codegen <input>)
- [Phase 09-01]: Use StrEnum instead of str+Enum for Backend enum — Python 3.11+ native, satisfies UP042 lint rule
- [Phase 09-01]: noqa: TC003 on Path import in codegen.py — Typer needs Path at runtime for option type introspection
- [Phase 09-02]: ModelData defined in models.py (not renderer.py) to avoid circular imports with 09-03 introspection layer
- [Phase 09-02]: uv_build includes non-.py files from src/ automatically — no pyproject.toml changes needed for templates
- [Phase 09-02]: Snowflake template generates TODO placeholders for TABLES/RELATIONSHIPS since SemanticView has no source table info
- [Phase 09-02]: Databricks uses SUM() placeholder with TODO comment since Metric() fields don't capture aggregation type
- [Phase 09-03]: Use inspect.getmembers() with inspect.isclass predicate + __module__ filter to exclude re-exported SemanticView subclasses
- [Phase 09-03]: Cast cls._fields to dict[str, Field] for strict basedpyright compatibility without type: ignore
- [Phase 09-03]: Non-fail-fast error collection: all files processed before raising typer.Exit(1) at the end
- [Phase 09-04]: Use typer.echo() for SQL stdout output rather than module-level Rich Console — CliRunner redirects sys.stdout at invoke time, not at module import time
- [Phase 09-04]: Use stdlib glob.glob() for absolute path glob patterns — Python 3.14+ Path.cwd().glob() raises NotImplementedError for absolute patterns
- [Phase 09-04]: Field instance docstrings use __dict__.get('__doc__') to avoid Metric/Dimension/Fact class docstrings appearing as per-field SQL comments
- [Phase 10-02]: conftest.py must live in src/cubano/ (not tests/) for --doctest-modules conftest discovery — pytest walks source tree for conftest files during doctest collection
- [Phase 10-02]: doctest_setup uses autouse=True with yield for guaranteed unregister("default") cleanup even on doctest failure
- [Phase 10-02]: NullsOrdering.__repr__ returns "NULLS FIRST" not "<NullsOrdering.FIRST: 'FIRST'>" — doctest expected output must match actual repr
- [Phase 10-02]: UP038: isinstance tuple syntax (X, Y) must use X | Y union syntax to satisfy ruff pre-commit hook
- [Phase 10-01]: docs dependency group kept separate from dev group for CI separation (docs deps not needed in test matrix)
- [Phase 10-01]: Stub guide pages created inline with Task 2 to satisfy mkdocs build --strict before Task 3 replaces with full content
- [Phase 10-01]: gen_ref_pages.py skips __init__, __main__, conftest, and private modules (underscore-prefixed) from API reference
- [Phase 10-01]: mkdocstrings uses google docstring style with table section style matching existing codebase docstrings
- [Phase 10]: SnowflakeCredentials/DatabricksCredentials from cubano.testing.credentials documented as primary credential loading pattern in backend guides
- [Phase 10]: Databricks codegen output documented as YAML (metric view format) not SQL — matches actual Jinja2 template output
- **Phase 10.1-01 (Query Refactor - Foundation):** Model.query() as primary entry point (not procedural Query()), expanded reserved names to all builder methods, field ownership validation prevents cross-model mixing, _model tracked on Query with init=False/repr=False
- **Phase 10.1-02 (Field Operators):** Operator overloads (__eq__, __ne__, __lt__, __le__, __gt__, __ge__) return Q objects for Pythonic filter syntax. Query.where() is public API, .filter() kept for backward compatibility. Field.__hash__ preserved for set/dict usage.
- **Phase 10.1-05 (Test Migration & Integration):** Comprehensive test migration to model-centric API with 73 new tests covering Model.query(), field operators, where(), execute(), Result class, integration workflow. 100% coverage on core Phase 10.1 modules (models.py, query.py, results.py). Integration test validates all LOCKED decisions work together.
- **Phase 10.1-07 (API Removal & Constructor Private):** Remove old procedural Query API (Query.filter() and Query.fetch() completely deleted, no deprecation), make Query constructor private by renaming to _Query. Query no longer exported from public API; Model.query() is the only documented entry point. Backward compatibility explicitly removed to enforce model-centric pattern.
- **Phase 10.1-08 (API Migration Verification):** Verified all internal code and tests successfully migrated to new API. All docstring examples use Model.query().execute(), no references to old .filter() or .fetch() methods remain. All 453 tests pass, typecheck 0 errors, lint passes, all doctests pass.
- **Phase 10.1 (COMPLETE):** Model-centric API via Model.query(), reserved method names pattern for namespace safety, Field operator overloads returning Q objects, introspection via .metrics()/.dimensions(), eager execution via .execute() returning Result object. Query API fully refactored with old methods removed and constructor private. All quality gates passing: typecheck (0 errors), lint (0 errors), format (all formatted), tests (453 passed).
- **Phase 11-01 (CI pytest split):** CI test job split into two separate steps: unit tests (433 items via `pytest tests/`) in dedicated step with -n auto parallelization, doctests (26 items from src/ with 20 passing + 6 skipped) in separate step. No marker filter on unit tests (removed broken `-m "mock or warehouse"` per RULE 2). Each step produces independent GitHub Actions output section with distinct pytest summary line. Honors locked decision: doctest failures reported in separate section from unit test failures.
- **Phase 11-02:** cubano-jaffle-shop example updated to use Model-centric API and registry pattern for engine lifecycle. All 13 mock tests pass; 2 unexpectedly pass (XPASS) indicating MockEngine improvements. conftest.py uses cubano.register()/unregister() per test for lifecycle management.
- **Phase 12-01 (Snapshot Infrastructure):** syrupy>=5.1.0 added. SNAPSHOT_TEST_DATA (5 rows, integer values for Decimal safety). snapshot fixture override with credential scrubbing via path_value. snowflake_engine/databricks_engine fixtures auto-detect --snapshot-update for record vs replay. backend_engine parametrized fixture drives both backends from single test. SnapshotAssertion imported from syrupy.assertion (not syrupy) for basedpyright strict compatibility.
- **Phase 12-02 (Snapshot Query Tests):** 6 DRY test functions (12 pytest IDs) with SnapshotSales synthetic model. Type annotations required by basedpyright strict (Any for backend_engine, SnapshotAssertion for snapshot). MockEngine bootstrap for snapshot generation (temporarily force is_recording=False, generate, restore). noqa: ARG001 on backend_engine fixture parameter.
- **Phase 12-03 (CI Snapshot Integration):** --snapshot-warn-unused warns on stale snapshots without failing the build. No new CI jobs, steps, or secrets needed. MockEngine replay requires no warehouse credentials.
- **Phase 12-04 (Warehouse Testing Guide):** Developer guide in docs/guides/warehouse-testing.md covering backend_engine parametrized fixture, --snapshot-update recording workflow, replay mode, re-recording, stale cleanup, best practices, file format, and troubleshooting. Guide placed after Codegen CLI in MkDocs nav.
- **Quick-8 (dbt snapshot_sales_view macro):** Two-step DDL per backend (staging table first, then view on top). Snowflake uses NUMBER/VARCHAR; Databricks uses BIGINT/STRING. METRIC VIEW declares DOUBLE metrics over BIGINT source -- acceptable since actual types captured during --snapshot-update. Fallback raises compiler error for unknown target.type.
- **Quick-9 (pytest fixture warehouse setup):** Pytest fixtures are the correct home for test data lifecycle -- not dbt on-run-end hooks. snowflake_engine/databricks_engine create snapshot_sales_data + snapshot_sales_view before yield (is_recording mode) and drop them after yield. Setup uses try/finally + pytest.fail(); teardown uses try/except Exception with print warning.
- [Phase 10.1-03]: metrics() returns list[Metric] and dimensions() returns list[Dimension | Fact] — rich Field descriptor objects enabling IDE autocomplete; both return empty list for no-match (never raise)
- **Phase 13-01 (Phase 11 Verification):** Re-verified Phase 11 CI split: two separate pytest steps confirmed in ci.yml (lines 109-113). Doctests: 20 passed, 6 skipped (warehouse-dependent operator overloads). Unit tests: 445 passed (grown from 433 since Phase 11 due to Phase 12 snapshot tests). cubano-jaffle-shop confirmed using Model-centric API. DOCS-10 marked SATISFIED.
- **Phase 13-02 (Docs Accuracy Fix):** filtering.md lookup table corrected: __gte->__ge, __lte->__le (matches Field.__ge__ and Field.__le__ dunder names). index.md feature card updated: .filter()->.where() (documented API). All 11 v0.2 user-facing docs reviewed; only 2 factual inaccuracies found and fixed. DOCS-04 marked SATISFIED.
- **Phase 13-03 (Warehouse Testing Guide Accuracy Fix):** warehouse-testing.md corrected for 5 stale reference categories introduced when tests/ was restructured to tests/integration/ and constants renamed in Phase 12: conftest location, test file name, TEST_DATA constant (was SNAPSHOT_TEST_DATA), snapshot directory, and DATABRICKS_SERVER_HOSTNAME env var (was DATABRICKS_HOST). Guide now functional for new contributors.
- [Phase 13]: jaffle-shop example project must mirror the library's credential loading pattern (CUBANO_ENV_FILE priority chain) for INT-06 to be fully satisfied end-to-end — raw os.environ bypasses this chain
- [Phase 13]: Iterator[None] is correct return type for yield-based pytest generator fixtures under basedpyright strict (not -> None)
- **Phase 13.1-01 (Predicate Tree IR):** Predicate base is plain class (not dataclass) with __and__, __or__, __invert__ operators. And/Or/Not/Lookup are frozen dataclasses. 15 lookup subclasses are empty class bodies inheriting Lookup with type params. Q class completely removed; Predicate exported from cubano.__init__. Double negation (~~pred) produces Not(Not(pred)) with no simplification.
- **Phase 13.1-02 (Field Predicate Methods):** All 6 Field operator overloads rewritten to return typed Predicate nodes (Exact, Not(Exact), Lt, Lte, Gt, Gte) instead of Q objects. 10 named filter methods added (between, in_, like, ilike, startswith, istartswith, endswith, iendswith, iexact, isnull). lookup() escape hatch for arbitrary Lookup subclasses. Deferred imports in method bodies to avoid circular dependency. _check_name() helper for DRY validation.
- **Phase 13.1-03 (WHERE Clause Compiler):** match/case structural pattern matching for predicate tree compilation. Dialect.placeholder property (%s for Snowflake/Mock, ? for Databricks). build_select_with_params() returns (sql_template, params) for execution. render_inline() for display. build_select() delegates to parameterized pipeline + render_inline for backward compat. Empty In([]) compiles to "1 = 0". SnowflakeEngine/DatabricksEngine execute() pass bind params to cursor. LIKE wildcard escaping deferred to v0.3.
- **Phase 13.1-04 (Integration Wiring):** query.py _filters type changed to Predicate | None. where() accepts *conditions varargs with None filtering (filter None, AND non-None, combine with existing). Q class fully removed from all source, tests, docs, jaffle-shop. filtering.md rewritten for Field method-based API. All quality gates pass: 565 tests, 0 typecheck errors, 20 doctests pass.
- [Phase 13.1]: Use Any (not ScalarT TypeVar) for scalar lookups to satisfy basedpyright strict; tighten only In (Collection[Any]) and Between (tuple[Any, Any]) where distinction is meaningful
- [Phase 14]: navigation.tabs.sticky enabled for better UX on scroll; section index pages kept minimal as scaffolding for Plans 02-03; semantic-views.md has real intro content not just placeholder heading
- [Phase 14-02]: Tutorials use MockEngine for runnable examples without warehouse credentials; explanation page kept brief (49 lines) with vendor doc links; home page tagline frames Cubano for engineers who already have semantic views
- [Phase 14-03]: How-to guide headings use action verbs ("How to define models"); tabbed SQL placed inline after Python code; backend overview has 3 comparison blocks (SELECT, WHERE, ORDER BY) for DOCS-05
- [Phase 14-05]: Backend overview rewritten as practical connection guide; changelog footer-only via extra.social; schema-qualified view names in admonition tip
- [Phase 14]: blacken-docs -l 60 reformats all docs code blocks to 60-char width; real warehouse engines shown as primary examples with MockEngine as optional fallback
- [Phase 15]: Kept uuid import and credential fixtures (still used by engine fixtures); removed only test_schema_name, snowflake_connection, databricks_connection
- [Phase 17]: Use getattr() in SemanticViewMeta.__repr__ to satisfy basedpyright strict (metaclass cls doesn't see subclass ClassVars)
- [Phase 17]: _Query._replace() helper propagates _model (init=False field) through frozen dataclass replace() chain -- fixes pre-existing field ownership validation bug
- **Phase 18-01 (Fix DDL Examples):** Snowflake DDL uses valid CREATE OR REPLACE SEMANTIC VIEW with TABLES/DIMENSIONS/METRICS clauses. Databricks DDL uses CREATE VIEW ... WITH METRICS LANGUAGE YAML with YAML body in $ delimiters. Used matching field names (s.revenue, s.cost) for tutorial clarity. Skipped Databricks fact hint since YAML has no separate fact concept.
- [Phase 19]: Inline bold prose for warehouse divergence in how-to guides (not admonitions) — lighter, keeps reading flow; Fact mention added to semantic-views.md explanation page to prevent implying two-type system
- **Phase 20-01 (Introspection IR + Type Mapping):** IntrospectedField.data_type is str | None (None signals renderer to emit TODO comment for GEOGRAPHY/VARIANT/ARRAY etc). TYPE_CHECKING guard for IntrospectedView in Engine files prevents circular imports. DatabricksEngine/SnowflakeEngine get NotImplementedError stubs immediately when ABC gains abstract method. Type lookups normalized via .upper()/.lower() for case-insensitive handling.
- [Phase 20]: _to_pascal_case() duplicated in each engine file to keep files independent
- [Phase 20]: cast('dict[str, object]', type_obj) used for Databricks type_dict narrowing under basedpyright strict
- **Phase 20-03 (Python Renderer):** Intermediate _FieldContext/_ModelContext dataclasses decouple Jinja2 template from IntrospectedView IR. _DATETIME_TYPES frozenset for O(1) datetime check. format_with_ruff() is non-fatal: FileNotFoundError or non-zero exit returns source unchanged. Jinja2 trim_blocks/lstrip_blocks=True produces clean Python output with no stray blank lines.
- [Phase 20]: Plain str (not StrEnum) for --backend option: supports arbitrary dotted import paths like my.package.MyBackend
- [Phase 20]: _resolve_backend() raises typer.BadParameter for unknown/invalid specs; Typer handles exit code + message
- [Phase 20]: unittest.mock.patch('cubano.cli.codegen._resolve_backend') as test injection point for warehouse-free CLI tests
- [Phase 20]: How-to guide written goal-oriented (Diataxis how-to format): reverse codegen guide replaces forward codegen guide, data engineer audience assumed to have existing warehouse view
- [Phase 20.1]: Field(Generic[T]) with @overload __get__ -> Field[T] | T satisfies basedpyright strict overloads without type: ignore
- [Phase 20.1]: reportUnknown* exemptions added to pyproject.toml for unsubscripted Generic[T] usage in test suite — Python 3.13 PEP 696 TypeVar defaults would resolve at language level
- [Phase 20.1]: source= shown in repr only when set: Metric('order_id', source='ORDER_ID') aids debugging, consistent with Django db_column= convention
- [Phase 20.1]: normalize_identifier() is abstract on Dialect — Snowflake=UPPER, Databricks=lower, Mock=identity. MockDialect identity keeps all existing test assertions green
- [Phase 20.1]: IntrospectedField.source_name is None for standard UPPERCASE Snowflake columns (ORDER_ID -> order_id -> ORDER_ID round-trips); set only for quoted-lowercase columns where python_name.upper() != original_col_name
- [Phase 20.1/21]: WHERE predicates store Python field_name strings AND optional source= override (Lookup.source field with repr=False); column resolution in _compile_predicate mirrors _resolve_col_name: use source verbatim when set, else normalize_identifier(field_name)
- [Phase 20.1]: data_type=None and data_type.startswith("TODO:") both map to "Any" in rendered output; needs_any flag controls 'from typing import Any' import
- [Phase 20.1]: CubanoViewNotFoundError and CubanoConnectionError subclass RuntimeError — backward-compatible typed exceptions for CLI exit code routing without breaking existing except RuntimeError callers
- [Phase 20.1]: CLI exit codes: EXIT_INVALID_BACKEND=2, EXIT_VIEW_NOT_FOUND=3, EXIT_CONNECTION_ERROR=4; epilog in app.command() in __init__.py so codegen() docstring stays clean
- [Phase 20.1]: Two-pass ruff pipeline: ruff format (style) then ruff check --fix --select I (isort); each pass has independent fallback
- [Phase 20.1]: Typer epilog double-newline: single \n collapses to space; use \n\n for preserved paragraph breaks in --help exit code list
- [Phase 20.1]: Rich color for CLI exit codes: green=0 success, yellow=1/2 user-fixable, red=3/4 system/connection errors
- [Phase 20.1]: Ruff isort alphabetizes from-import names: from cubano import Dimension, Fact, Metric, SemanticView (alphabetical, not template order)
- [Phase 20.1]: Typed subscripts documented as recommended (not required) in models.md — untyped Metric() documented as shorthand for Metric[Any](), valid Python just without type narrowing
- [Phase 21]: repr=False on Lookup.source preserves existing repr assertions and excludes source from predicate identity
- [Phase 21]: node.source accessed via match variable (not pattern-matched f) in _compile_predicate — mirrors _resolve_col_name exactly
- [Phase 22]: Two targeted string replacements only in codegen.md — SHOW COLUMNS IN VIEW and SNOWFLAKE_ACCOUNT corrections — no prose rewrites
- [Phase 23]: CubanoViewNotFoundError and CubanoConnectionError exported from cubano.__init__ via engines.base import
- [Phase 23]: Result exported alongside Row from cubano.__init__ via results import
- [Phase 23]: CODEGEN-WAREHOUSE added to REQUIREMENTS.md traceability table (Phase 20, Complete)
- [Phase 23]: CODEGEN-REVERSE description corrected: warehouse->Python direction (Phase 20, cubano codegen <schema.view_name>)
- [Phase 24]: INT-06 claimed by multiple Phase 08 plans (08-01, 08-05, 08-06) — each addressed a distinct aspect of credential loading; multiple plans satisfying same requirement is permitted
- [Phase 24]: 20-02 requirements-completed uses [] to avoid double-counting CODEGEN-WAREHOUSE/REVERSE with 20-04 which already claimed them
- [Phase 24-01]: _eval_predicate() key resolution: node.source verbatim when set, field_name as fallback (MockDialect=identity, no case folding)
- [Phase 24-01]: fnmatch.fnmatchcase() used for LIKE/ILIKE in _eval_predicate: translates % -> * and _ -> ?, no external deps
- [Phase 24-02]: CODEGEN-01-08 annotated as SUPERSEDED via HTML comment (not deleted) — retains historical record while making current state clear
- [Phase 24-02]: Phase 19 requirements field set to [] — Phase 19 documented Fact fields, not Predicate composition; DOCS-04 was incorrectly assigned
- [Phase 24-04]: [Phase 24-04]: --snapshot-update with credentials uses real warehouse; for CI MockEngine bootstrap with credentials present, manually write .ambr entries in MockEngine column format (plain revenue/cost names, not measure() wrappers from real metric views)

### Roadmap Evolution

- v0.1 shipped with 7 phases + 7.1 (CI/CD inserted) — completed 2026-02-16
- v0.2 roadmap created with 3 phases (8-10) — 2026-02-17
- Phase 10.1 inserted after Phase 10: Refactor Query Interface to Model-Centric (URGENT) — 2026-02-17
- Phase 13.1 inserted after Phase 13: Implement filter lookup system and WHERE clause compiler (URGENT) — 2026-02-22
- Phase 18 added: Fix invalid CREATE VIEW examples in first-query tutorial — 2026-02-23
- Phase 19 added: Document Fact field type for Databricks and Snowflake users
- Phase 20 added: Reverse codegen: introspect warehouse semantic view and generate Cubano Python model class — 2026-02-23
- Phase 20.1 inserted after Phase 20: UAT gap identified re quoted vs unquoted column names and cubano model field (URGENT)

### Pending Todos

1. **Add a query interface to the CLI** — `2026-02-18-add-a-query-interface-to-the-cli.md`
2. **Bidirectional codegen** — `2026-02-18-bidirectional-codegen.md`
3. **cube.dev and dbt-sl backends** — `2026-02-18-cube-dev-and-dbt-sl-backends.md`
4. **django-cubano wrapper** — `2026-02-18-django-cubano-wrapper.md`
5. **cubano-graphql interface** — `2026-02-18-cubano-graphql-interface.md`
6. **django-ninja integration with multipart/mixed JSON + Arrow response** — `2026-02-18-django-ninja-integration-multipart-arrow.md`
7. **DataFrame-agnostic result output via Arrow** — `2026-02-18-dataframe-agnostic-result-output-via-arrow.md`
8. **FastAPI integration enhancements** — `2026-02-18-fastapi-integration-enhancements.md`
9. **MCP tools and agent skills interface** — `2026-02-18-mcp-tools-and-agent-skills-interface.md`
10. **Support all auth schemes for each backend provider** — `2026-02-19-support-all-auth-schemes-for-each-backend-provider.md`
11. **Review and extend filter lookup expressions** — `2026-02-19-review-and-extend-filter-lookup-expressions.md`
12. **DB migrations system** — `2026-02-20-db-migrations-system.md`
13. **Evaluate SQLAlchemy as cubano foundation** — `2026-02-20-evaluate-sqlalchemy-as-cubano-foundation.md`
14. **Implement filter lookup system and WHERE clause compiler** — `2026-02-20-implement-filter-lookup-system-and-where-clause-compiler.md`
15. **Quality gate typecheck with multiple checkers for library consumers** — `2026-02-20-quality-gate-typecheck-with-multiple-checkers-for-library-consumers.md`

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 4 | update docs to reflect the Query->Model.query api refactor from phase 11 | 2026-02-18 | 9f9f439 | Verified | [4-update-docs-to-reflect-the-query-model-q](.planning/quick/4-update-docs-to-reflect-the-query-model-q/) |
| 5 | format docs Python code examples to match ruff/black style (blacken-docs -l 100) | 2026-02-18 | 8d7251b | Complete | [5-format-docs-code-examples-to-match-ruff-](.planning/quick/5-format-docs-code-examples-to-match-ruff-/) |
| 6 | restructure docs layout: move docs content to docs/src/, gen_ref_pages.py to docs/scripts/ | 2026-02-19 | 94e33d6 | Verified | [6-restructure-docs-layout-move-docs-conten](.planning/quick/6-restructure-docs-layout-move-docs-conten/) |
| 7 | .cubano.toml role arg support: SnowflakeCredentials.load() role override + snowflake_engine fixture fix | 2026-02-19 | 250ca0e | Complete | [7-the-loader-for-cubano-toml-files-needs-t](.planning/quick/7-the-loader-for-cubano-toml-files-needs-t/) |
| 8 | dbt macro creating snapshot_sales_view as Snowflake SEMANTIC VIEW or Databricks METRIC VIEW with 5 SNAPSHOT_TEST_DATA rows | 2026-02-19 | 0675e38 | Complete | [8-update-dbt-jaffle-shop-to-set-up-the-exp](.planning/quick/8-update-dbt-jaffle-shop-to-set-up-the-exp/) |
| 9 | revert dbt macro (quick-8) and add snapshot_sales_data/snapshot_sales_view CREATE/DROP to pytest fixtures directly | 2026-02-19 | 906af20 | Verified | [9-revert-dbt-jaffle-shop-snapshot-view-cha](.planning/quick/9-revert-dbt-jaffle-shop-snapshot-view-cha/) |
| 10 | fix docstring Example: sections in engine API reference (# comments rendered as headings) | 2026-02-23 | fb145f7 | Complete | [10-fix-docstring-examples-in-reference-api-](.planning/quick/10-fix-docstring-examples-in-reference-api-/) |
| 11 | fix remaining bare # comments in docstring Example: sections (base.py, mock.py, sql.py) | 2026-02-26 | 0054bb4 | Complete | — |
| 11.1 | fix CI test failures: set _TYPER_FORCE_DISABLE_TERMINAL in pytest_configure to suppress ANSI codes | 2026-02-26 | 6f9bf3e | Verified | [11-fix-ci-test-failures](.planning/quick/11-fix-ci-test-failures/) |

### Blockers/Concerns

Research-flagged attention areas for v0.2 planning:
- **Phase 10:** Doctest validation tooling availability (implement in CI as fallback)

### Coverage Validation

v0.2 Requirements mapped to phases:

| Phase | Requirements | Count |
|-------|--------------|-------|
| 8. Integration Testing | INT-01, INT-02, INT-03, INT-04, INT-05, INT-06 | 6 |
| 9. Codegen CLI | CODEGEN-01 through CODEGEN-08 | 8 |
| 10. Documentation | DOCS-01 through DOCS-10 | 10 |
| **Total v0.2** | | **24** |

**Status:** v0.2 milestone complete

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 24-04-PLAN.md — Phase 24 fully complete (all 4 plans done)
Next: Phase 24 complete. test_filtered_by_dimension reinstated with MockEngine snapshots. v0.2 tech debt cleanup done. Deferred: docs/src/reference/cubano/codegen/models.md stale reference (quick fix). Ready for next milestone work item.
