# Phase 55 summary: codegen hardening (55-01 to 55-04)

Executed 2026-10-15 on branch `claude/phase-55`. Covers 55-01 to 55-04 only; 55-05 (the D9
checkpoint) and 55-06 (implementing D9) are separate. No per-plan PLAN.md files were
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

- 55-05 / 55-06 (D9, GEN-11, GEN-12), including the "Only an annotation moves a row to
  drift" sentence in `how-to/codegen.rst`.

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
