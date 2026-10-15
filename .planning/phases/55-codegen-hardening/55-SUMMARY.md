# Phase 55 summary: codegen hardening (55-01 to 55-06)

Executed 2026-10-15 on branch `claude/phase-55`. 55-05 (the D9 checkpoint) is recorded in
`.planning/research/2026-10-15-D9-DECISION.md`; 55-06 (implementing D9, on the stacked branch
`claude/phase-55-06`) has its own section at the end. No per-plan PLAN.md files were
written: each plan was run test-first from the ROADMAP success criteria and REQUIREMENTS,
a failing-test commit followed by the fix.

## Done

| Plan | Requirement | What changed |
|---|---|---|
| 55-01 | GEN-01 | `codegen` refuses an introspected view whose class name is not an identifier (a custom `--backend` engine's `2024Sales`, `class`, an injected statement) and two views folding to one name (`emea.sales`, `apac.sales` -> `Sales`), exit 2 naming the views. One rule, `query_resolver.find_class_name_problem` on top of `is_valid_class_name`, now also used by `codegen-dto`'s `_named` (messages unchanged). Both commands `ast.parse` the rendered module (`python_renderer.check_parses`) before formatting or emitting; a failure exits 1 and writes nothing. |
| 55-01 | GEN-02 | An installed ruff that cannot start or exits non-zero raises `GeneratedSourceError` with ruff's stderr; both commands exit 1 and write nothing. ruff being absent is still the documented degrade. |
| 55-02 | GEN-03 | A connection-config `ValidationError` prints field path and error type only (`account (missing)`), never `input_value` and never `msg`. |
| 55-02 | GEN-04 | `semolina.cli.codegen.exit_code_for(error, stage=)` is the one table; both commands go through `exit_for`. Setup: BadParameter and a missing driver extra -> 2, driver/connection errors -> 4. Warehouse: view not found 3, connection 4, untranslated `adbc_driver_manager.Error` 6, RuntimeError/ValueError 1; unlisted exceptions propagate. A dotted `--backend` whose constructor needs arguments or raises is 2. `EXIT_PROBE_FAILED` moved to `cli/codegen.py`; `codegen` now documents 6. |
| 55-03 | GEN-05 | Source is echoed with `nl=False`; `> file` and `--output file` are byte-identical and pass `ruff format --check --isolated`. Two syrupy snapshots lost the stray blank line. |
| 55-03 | GEN-06 | `codegen --output/-o`. One writer, `emit_source`, for both commands: once, after every view rendered, through a temp file and `os.replace`, keeping the target's mode. `check_output` (moved from `dto_codegen`) refuses a missing directory before connecting. `codegen --check` reads the `--output` file; `--model` stays as the older spelling; both together exit 2. |
| 55-03 | GEN-07 | Both ruff passes run `--isolated`. |
| 55-04 | GEN-08 | `~` expands before the join for `database` and `output` in `[tool.semolina.dto]`. `DUCKDB_DATABASE` overriding a committed `database` prints a note naming both paths. |
| 55-04 | GEN-09 | `Any` and `Any \| None` compare equal in `--check`, so an untyped `Metric()` on an untyped column matches; on a typed column it still drifts. `codegen --check` exits 6 when any row was compared against metadata, ahead of 5. |
| 55-04 | GEN-10 | `cli/utils.py` and `tests/unit/codegen/test_utils.py` deleted. |
| 55-04 | docs | `how-to/codegen.rst` documents `--output`, `--check --output`, the new exit-6 meanings and untyped metrics; `reference/cli.rst` and `how-to/dto-codegen.rst` updated; epilogs agree. |

## Commits

| SHA | Subject |
|---|---|
| `c31a788` | test(codegen): failing tests for the validity gate and a loud ruff failure |
| `1f26301` | fix(codegen): refuse unusable class names and never emit unparseable source |
| `68c65b0` | docs(planning): 55-01 done |
| `63b20f0` | test(cli): failing tests for credential redaction and one exit-code table |
| `2874469` | fix(cli): redact config errors; one exception-to-exit table for both commands |
| `2935dcb` | docs(planning): 55-02 done |
| `aa9b9ca` | test(codegen): failing tests for output plumbing |
| `77c9c31` | fix(codegen): byte-identical stdout and --output, atomic writes, isolated ruff |
| `2f9c04d` | docs(planning): 55-03 done |
| `da0d4aa` | test(codegen): failing tests for config paths, env override note, check accuracy |
| `bd24499` | fix(codegen): expand ~ in DTO config, announce env override, honest --check |
| `d4d3850` | refactor(cli): remove dead cli/utils.py and its tests |
| `a2c6747` | docs(codegen): document --output, --check reading it, and the new exit 6 |

## Tests changed rather than added

- GEN-02 inverted three `TestFormatWithRuff` tests that pinned the silent fallback.
  `TestRenderAndFormat.test_fallback_when_ruff_unavailable` simulated "unavailable" with a
  process that could not start; it now patches `ruff_available`.
- GEN-05 regenerated two snapshots (one blank line each).
- GEN-10 deleted the four tests of the dead functions.
- Two failing-first commits declared the new symbol as a stub (`GeneratedSourceError`, an
  `exit_code_for` raising `NotImplementedError`) so the suite type-checks; every red was
  behavioural, not an ImportError.

## Judgement calls

- **GEN-01 exit codes.** An unusable or colliding class name is 2 (it comes from the view
  arguments, and `codegen-dto` uses 2 for the same check); a parse failure is 1.
- **GEN-02.** A ruff failure is an error (exit 1, nothing written), not a warning with
  unformatted output, since emitting would break GEN-05.
- **GEN-04.** A missing driver extra is 2 with a `pip install 'semolina[<backend>]'` hint.
  An untranslated driver error while describing a view is 6 on `codegen` too, so one
  exception at one stage has one code. Constructor failures other than connection errors
  are 2.
- **GEN-07.** `--isolated` (ruff defaults) rather than resolving config against the output
  path, which would have made `> file` and `--output file` differ. A project with its own
  ruff settings should check the file with `--isolated` or exclude it; the how-to says so.
- **GEN-08.** `output` got the same `~` fix as `database`. Only an environment override
  is announced; a typed `--database` is not.
- **GEN-09.** "No drift for untyped `Metric()`" is read narrowly: `Any` equals `Any | None`,
  `Any` is not a wildcard (consistent with D5). The fallback exit is 6 (`EXIT_PROBE_FAILED`),
  not a new code. It fires when any row used the metadata route, not only when the whole
  probe failed, and outranks drift. D9's open question 3 (fail by default or under a flag)
  is therefore answered "by default" here; 55-05 may revisit.
- **`codegen --check` on a missing file** still exits 1 (`codegen-dto` exits 2). Left as is
  rather than changing an existing test's contract.

## Gates (last run, after 55-04)

- `uvx prek run --all-files`: pass.
- `uv run pytest -n auto -q`: 2018 passed, 16 skipped, 2 xfailed.
- `semolina-jaffle-shop`: 13 passed.
- Docs: `sphinx-build -W` pass.
- Python 3.11: `tests/unit/codegen/` 695 passed. The isolated env needs
  `--with-editable '.[duckdb,pyarrow,arrowmodel]' --with syrupy --with ruff`; without the
  extras unrelated DuckDB and arrowmodel tests error.

## Left for later

- ~~55-05 / 55-06 (D9, GEN-11, GEN-12)~~: done, see "55-06: D9 implemented" below.

## PR #56 review fixes

Test-first: `914bb33` (18 red cases, each confirmed red; one guard), then `af37c4c`
(fixes) and `bb8ac72` (docs).

- **Import-shadowing class names.** `find_class_name_problem` takes the caller's
  `module_names` and refuses a class the module binds (`analytics.metric` -> `Metric`,
  `--name Any`), exit 2 naming the view or entry. `codegen` passes
  `GENERATED_MODULE_NAMES`; `codegen-dto` passes the new `dto_renderer.DTO_MODULE_NAMES`,
  built from the import block's own constants and pinned by a sync test that parses the
  block. `--name Metric` stays legal on `codegen-dto`.
- **Exit 6 on `codegen --check`** now means the probe failed (`probe_error`). This
  supersedes the GEN-09 judgement above: a probe that ran but carried no column for one
  field no longer exits 6, and its note names the fields instead of "probe unavailable".
- **Custom `--backend` `ValidationError`** goes through `_redacted_validation_summary`.
- **`--output`** resolves symlinks before naming the temp file, writes in place to an
  existing non-regular target (`/dev/stdout`, a FIFO), and removes the temp file on any
  exception, `KeyboardInterrupt` included.
- **`~nosuchuser`** in `[tool.semolina.dto]` is a config error (exit 2), not a traceback.
- **`codegen sales sales`** dedupes the repeat, first occurrence first.
- **Docs.** `codegen-dto`'s exit 1 and 2 cases listed in the epilog, `reference/cli.rst`
  and `how-to/dto-codegen.rst`; "committed file" wording in `how-to/codegen.rst`; the
  `dto_codegen` module docstring no longer contradicts the shared exit table.

Gates after the fixes: prek pass; `pytest -n auto`: 2046 passed, 16 skipped, 22 xfailed
(strict xfails unchanged); jaffle-shop 13 passed; `sphinx-build -W` pass.

## 55-06: D9 implemented

D9 was decided 2026-10-15: griffe (`griffelib`) reads committed files for both `--check`
commands. Paul answered the reader question; the rest took defaults recorded as D9.1-D9.8
in the decision note and REQUIREMENTS. Branch `claude/phase-55-06`, stacked on PR #56.

Commits: `6ea67db` dependency, `8d3dc69` failing tests (beyond the corpus), `03b6e81`
implementation (flips the corpus), `b01114d` docs.

| Requirement | What changed |
|---|---|
| GEN-11 | `codegen/static_reader.py` loads the committed file with griffe (`allow_inspection=False`; search path = the file's package root, found from `__init__.py` files, and the working directory). It resolves names through the file's imports, follows base classes into other modules in method resolution order, and reads string constants across modules. Nothing is imported or run; a test proves imported modules are not executed. `codegen/type_compare.py` is B: annotations reduced to codegen's spelling with names resolved inside an allowlist (`builtins`, `typing`, `decimal`, `datetime`, `uuid`, `semolina`, `pydantic`, ...); anything else falls back to comparing the text, as before. |
| GEN-12 | Both readers return warnings (`read_committed_model_file`, `read_committed_dto_file`; the list-returning functions remain) for every field-like statement, `view=`, `source=`, alias or base class they cannot read, naming class, line and statement. Both CLIs print them as `Warning:` lines. Every corpus case is a passing test or a pinned limitation; `how-to/codegen.rst` no longer says only an annotation moves a row to drift. |

R rules: view names fold like DuckDB identifiers (`normalize_view_name`); every class for a
view is checked, each table titled with its class when there are several; a renamed
attribute is matched by the column it reads (`annotation_check._match_renamed_fields`, with a
Detail line naming the attribute); a renamed DTO class is matched by its provenance docstring
(`dto_reader.has_provenance`, with a Note). `AliasChoices` in a generated DTO class binds each
choice; a match through it carries a detail that `.into()` refuses the construct.

Corpus (`tests/unit/codegen/test_check_accuracy_corpus.py`), no xfails left:

- Fixed, marker removed: M1 x4, M2 x3, M3 x2, M4 x2, M5, M6 x2, M9, D1 x2, D2
  (`AliasChoices`), D4.
- Limitations D9 accepts: D3 (`test_there_is_no_way_to_judge_by_validate_true` replaces the
  xfail), M10 and D5 (already passing; docstrings point at the D9 note).

Judgement calls:

- `test_dto_cli.py::test_a_missing_class_is_reported_by_name` pinned a renamed class (with
  its provenance docstring) as missing plus extra, which D4 reverses. Its setup now also
  points the docstring at another query, so it still tests the missing-plus-extra report
  with unchanged assertions; a new test beside it pins the D4 match.
- A DTO field matched through `AliasChoices` is a match (D9.1), with a detail noting that
  `.into()` refuses `AliasChoices`. `_is_generated` still does not count `AliasChoices`, so a
  hand-written class using it stays out of the report (the existing test still holds).
- A DTO field with a default is now a warning rather than a silent skip (GEN-12).
- DTO base classes are followed too, not only model bases.
- `docs/src/conf.py` ignores `griffe.*` and `ast.expr` reference targets, which the new
  modules' signatures bring into the API reference.

Gates: prek pass; `pytest -n auto`: 2145 passed, 16 skipped, 2 xfailed (both in other
files); jaffle-shop 13 passed; `sphinx-build -W` pass; Python 3.11 `tests/unit/codegen`
818 passed, and 818 passed again with `griffelib==2.0.0` (the floor).

## PR #56 review fixes, round 2

Test-first: `dccc8a9` (red tests, each case watched fail), then `40564bb` (fixes) and
`5f5187a` (docs). `f5062ff` fixes a CI hang in a test.

- **Derived class names steer clear of module imports.** `introspector.class_name_for`
  takes a `reserved` set (default `GENERATED_MODULE_NAMES`) and prefixes a hit with `View`,
  as it does keywords: `analytics.metric` -> `ViewMetric`, so built-in backends no longer
  exit 2 on it. `codegen-dto` passes its own sets: a query attribute gets `Query`
  (`any` -> `QueryAny`, `none` -> `QueryNone`); a view avoids both modules' imports, so
  its DTO keeps its model's name. The refusal stays as the backstop for a custom engine's
  or `--name`'s own choice, with a remedy that works.
- **NFKC.** Derived names are normalized; `find_class_name_problem` compares NFKC forms
  (`Ａny`, `Ｓales` vs `Sales`) and messages say what the name binds as.
- **`ValidationError` at the warehouse stage** is redacted in `exit_for`.
- **`codegen --check` on a missing file** exits 2 before connecting, as `codegen-dto` does;
  the test that pinned 1 encoded the divergence and now expects 2.
- **`--output`** writes in place when the directory refuses the temp file
  (`PermissionError`) and the target exists. Docs note the new-inode trade-off.
- **FIFO test hang (3.11 CI).** A blocking `open("wb")` guarded by `is_alive()` raced the
  reader closing; the read end is now opened non-blocking and drained with `select`.

Gates: prek pass; `pytest -n auto`: 2077 passed, 16 skipped, 22 xfailed (strict xfails
unchanged), also on 3.11; jaffle-shop 13 passed; `sphinx-build -W` pass; the FIFO test 50x
on 3.11, serial and `-n auto`.
