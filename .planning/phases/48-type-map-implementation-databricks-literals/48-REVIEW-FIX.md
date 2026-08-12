---
phase: 48-type-map-implementation-databricks-literals
fixed_at: 2026-08-12T00:00:00Z
review_path: .planning/phases/48-type-map-implementation-databricks-literals/48-REVIEW.md
iteration: 1
fix_scope: all
findings_in_scope: 12
fixed: 11
skipped: 0
status: all_fixed
---

# Phase 48: Code Review Fix Report

**Fixed at:** 2026-08-12
**Source review:** `.planning/phases/48-type-map-implementation-databricks-literals/48-REVIEW.md`
**Iteration:** 1

**Summary:**

| Finding | Outcome | Test commit | Fix commit |
|---|---|---|---|
| CR-01 | fixed | `ef2d340` | `70980c6` |
| CR-02 | fixed | `cde8696`, `1e9bcc4` | `f2142b1` |
| CR-03 | fixed (widened: the docstring channel too) | `655b21c` | `4705083` |
| WR-01 | fixed (scope call recorded below) | `ade8e4b` | `0df674c`, `ce6c67a` |
| WR-02 | fixed | `f6ca979` | `77e0c6d` |
| WR-03 | fixed | `0f6028e` | `dc0a5ca` |
| WR-04 | fixed | `f91909a` | `79dedfa` |
| WR-05 | fixed | — | `b4c1b0d` |
| WR-06 | fixed | `205e616` | `6a4513c` |
| IN-01 | fixed | `5f88ea4` | `652d2e4` |
| IN-02 | fixed | — | `888e189` |
| IN-03 | **confirmed clean — no change needed** | — | — |

- Findings in scope: 12
- Fixed: 11
- Confirmed with no change required: 1 (IN-03, which asked for an audit rather than an edit)
- Skipped: 0

Every Critical was reproduced first with the reviewer's own payload, and every reproduction
was confirmed red before the fix and green after. Nine of the twelve findings ship with a
regression test; WR-05 is prose, IN-02's reproduction is a working-directory change rather
than a test, and IN-03 asked only that the imports be checked.

**Fifteen files changed** — nine under `src/`, five under `tests/`, one under `docs/`. No
`# type: ignore` was added (`git diff e47e281..HEAD -- src/ | grep -c '^+.*type: ignore'`
returns 0). `47-DECISIONS.md` was not touched.

## Scope fence

`git diff e47e281..HEAD --stat -- src/semolina/cursor.py src/semolina/acursor.py
src/semolina/results.py` is **empty**. No value coercion was added anywhere: the phase's
`--check` and rendering paths changed what the report *says* and what the generator
*quotes*, never what a `Row` holds. `tests/unit/test_scope_fence.py` passes.

## Verification environment

All gates ran **inside the isolated worktree** `/tmp/claude-501/sv-48-reviewfix-h5Gp9a`
(branch `gsd-reviewfix/48-23373`), whose `.venv` was synced with
`uv sync --all-groups --extra all` so the `docs` group was present. The worktree was then
fast-forwarded into `gsd/v0.7-async-typed-results` and removed.

**The root suite was re-run in the main checkout after the fast-forward** and reproduces
identically at 1316 passed / 16 skipped / 2 xfailed, so the headline number does not depend
on a worktree that no longer exists. The remaining gates below were measured in the
worktree.

| Gate | Result |
|---|---|
| `uv run pytest` (root) — **worktree and main checkout** | **1316 passed, 16 skipped, 2 xfailed** (baseline 1288/16/2 — +28 new tests, 0 regressions) |
| jaffle-shop `uv run pytest` | **16 passed, 15 skipped** — matches baseline exactly |
| `prek run --all-files` | all hooks passed (ruff, ruff-format, uv-lock, basedpyright strict, blacken-docs) |
| `just docs-build` | build succeeded under `-W` |
| `just type-fidelity` then `git status` | **no diff** — `47-TYPE-FIDELITY.md` regenerates byte-identically |
| `tests/unit/test_scope_fence.py` | passed |
| syrupy snapshots | 3 passed — the generated-model output is byte-identical despite CR-03 |

The 28 new tests break down as CR-01 5, CR-02 5, CR-03 5, WR-01 4, WR-02 2, WR-03 1,
WR-04 2, WR-06 2, IN-01 2.

**One thing to confirm by eye rather than by gate:** `prek`'s pinned ruff is v0.9.6 while
the project's `uv run ruff` is newer, and they disagree twice (UP038 and one D301 the
newer one does not raise). Both were resolved to satisfy the pinned hook, which is the
gate that matters.

## Fixed Issues

### CR-01: The drift report parsed its own payload as Rich markup

**Files modified:** `src/semolina/cli/codegen.py`, `tests/unit/codegen/test_cli.py`
**Commits:** `ef2d340` (tests), `70980c6` (fix)

Every interpolated value in this module now goes through a new `_labelled()` helper or a
bare `rich.text.Text`, which carries styling as an attribute instead of as embedded tags
and so bypasses the markup parser entirely. The status cell keeps its red/green as a
`Text` style argument.

**Widened past the three sites the review named.** The review cited the table, the
fallback note, and `_run_check`'s `{view_name!r}` line. The seven `f"[bold red]Error:[/bold
red] {e}"` prints are the same defect with the same source — `e` is a driver or warehouse
exception whose message routinely quotes the offending identifier — so all of them were
converted too. The one remaining markup string in the file is the ruff-missing hint, which
interpolates nothing and already escapes its own brackets.

**Verified.** Four of the five new tests were red first, two of them on the exact
reproductions in the review:

- `list[str] | None` and `list[int] | None` printed as two identical `list | None` cells;
  they now print in full.
- `[/red]` as a field name exited the CLI with `MarkupError("closing tag '[/red]' at
  position 182 doesn't match any open tag")` and exit code 1; it now reaches
  `EXIT_VIEW_NOT_FOUND`.
- `test_the_status_cell_is_still_styled` is the guard against over-correcting: it asserts
  the ANSI codes `\x1b[32m` and `\x1b[31m` are still emitted and that no literal `[green]`
  survives. It needs `no_color=False` because `tests/conftest.py` sets `NO_COLOR=1` for the
  whole suite, which strips colour while leaving every other attribute — without that the
  test would have passed vacuously against an empty channel.

### CR-02: `--check` fed catalogue-returned field names into an unescaped SQL literal

**Files modified:** `src/semolina/engines/sql.py`, `src/semolina/engines/duckdb.py`,
`tests/unit/test_sql.py`, `tests/unit/codegen/test_annotation_check.py`
**Commits:** `cde8696` (tests), `1e9bcc4` (tightened assertions), `f2142b1` (fix)

**Fixed in the builder, not at the `--check` call site**, as the review recommended — and
routed through the escaper the repo already had rather than adding a second one.
`_sql_str_literal` was promoted from `src/semolina/engines/duckdb.py` into
`src/semolina/engines/sql.py` as public `sql_str_literal`, and `duckdb.py` now imports it
back under its old private name. There is no circularity risk: `duckdb.py` already reaches
`sql.py` transitively through `engines/base.py`. `DuckDBSQLBuilder.build_select_with_params`
now routes the view name and all three field lists through it.

Fixing the builder rather than the caller also makes `probe.py`'s module docstring true.
It asserts safety by trusting `build_select_with_params` (threat T-48-14); the wrapper was
already clean and the builder now is too, so the claim no longer rests on a false premise.

**Verified.** Five tests, all confirmed red first by stashing only the two source files.
The reviewer's payload reproduces exactly:

```
- dimensions := ['x'') FROM read_csv(''/etc/passwd'') --'])   (after)
+ dimensions := ['x') FROM read_csv('/etc/passwd') --'])      (before)
```

**The first assertions I wrote were wrong, and the correction is its own commit
(`1e9bcc4`).** `sql.count("FROM") == 1` fails even on correctly escaped output, because the
escaped payload still *contains* the word `FROM`. The tests now strip every single-quoted
literal with a pattern that consumes a doubled `''` as content, and assert the remaining
SQL is the shape it would have had for a well-behaved name:
`SELECT *\nFROM semantic_view(<literal>, dimensions := [<literal>])`. That is the property
that matters, and it fails loudly for an unescaped quote because the payload then falls
outside a `<literal>` marker.

`tests/unit/codegen/test_annotation_check.py::TestCatalogueNamesReachSqlEscaped` walks the
shipped `_canonical_model` → `_build_query` → builder chain rather than the builder alone,
because the data flow is the new part; the quoting bug itself predates the phase.

### CR-03: A catalogue-supplied `source_name` injected arbitrary Python into a generated model

**Files modified:** `src/semolina/codegen/python_renderer.py`,
`src/semolina/codegen/templates/python_model.py.jinja2`,
`tests/unit/codegen/test_python_renderer.py`
**Commits:** `655b21c` (tests), `4705083` (fix)

No raw warehouse string reaches the template any more. `_FieldContext.source_name` became
`source_literal` and `_ModelContext.view_name` became `view_literal`, both pre-quoted by a
new `_python_str_literal()`; the template interpolates the finished literal. Jinja
autoescaping was not used — it escapes for HTML, which would turn `&` in a column name into
`&amp;` while leaving a quote just as dangerous.

**`repr()` with the delimiters swapped back, not bare `repr()`.** `repr` prefers single
quotes, so a bare `repr` would have changed `source="order_id"` to `source='order_id'` in
every generated file — breaking `test_source_name_set_emits_source_kwarg` and the e2e
snapshot for a cosmetic reason, and only being tidied up by ruff for users who install the
optional `codegen-lint` extra. `_python_str_literal` swaps back to double quotes when the
body carries no `"` to escape, which is byte-identical to today's output for every name
without a quote in it. The 3 syrupy snapshots confirm this.

**I widened this to a third channel the review did not name.** The finding note asked
whether the same channel appears elsewhere in the template; it does.
`"""{{ field.docstring }}"""` interpolates a column COMMENT, which is warehouse metadata
from the same catalogue. A description of `ends the docstring """ ; import os; ...` closes
the literal and executes at import time exactly as `source_name` did. That one is escaped
rather than `repr`'d, deliberately: `repr` would collapse a multi-line column comment onto
one line with `\n` escapes, and a field docstring is something the user reads.
`_docstring_body` escapes every `\` and every `"` — every one, rather than only the runs
that would actually terminate the literal, because a rule that has to reason about run
lengths and trailing positions is a rule that gets an edge case wrong (`""` immediately
before the closing delimiter breaks it, and so does a lone trailing `"`).

**Verified.** Five tests, four red first. As with CR-02, my first assertion
(`"import os" not in source`) was wrong for the same reason and was replaced before
committing: a payload safely inside a literal still contains that text. The tests now parse
the generated source with `ast.parse` and assert two things — the payload is recoverable as
an `ast.Constant` string, and every top-level statement is an `Import`, `ImportFrom` or
`ClassDef`. `test_a_multi_line_description_still_renders_as_a_docstring` guards against the
escape costing the readable rendering.

`view_name` also got the treatment. It is argv-sourced so lower value, as the review said,
but it is the same escape and there is no reason to leave it.

### WR-01: `--check` parsed the field role and `source=` and compared neither

**Files modified:** `src/semolina/codegen/annotation_check.py`, `src/semolina/cli/codegen.py`,
`tests/unit/codegen/test_annotation_check.py`
**Commits:** `0df674c` (inert `detail` field), `ade8e4b` (tests), `ce6c67a` (fix)

**The scope call, made and recorded rather than picked silently: compare both, but compare
the *resolved* column rather than the raw `source=`.**

The role is not a user preference. `Metric` and `Dimension` land in different
`semantic_view()` clauses, and while a metric's probed annotation gains `| None` — so some
role changes already surface as annotation drift — `Dimension[int | None]` against a
warehouse metric compares equal and the model is still wrong. It is compared directly.

`source_name` needed more care, and this is where I diverged from the review's suggested
snippet. The review proposed `(committed.source_name or None) == (field.source_name or
None)`, which compares the raw overrides. That produces false drift for a documented
workflow: `docs/src/how-to/codegen.rst` has a whole section on adding `source=` by hand, and
the warehouse reports `source_name=None` for any column whose name already round-trips
through `normalize_identifier`. A user who writes `source="COUNTRY"` on a field the dialect
already resolves to `COUNTRY` builds byte-identical SQL and would have been told their model
had drifted.

The comparison is therefore on `source or normalize_identifier(name)` — exactly
`SQLBuilder._resolve_col_name`'s rule, so `--check` compares what the query will actually
select. The review's OLD-vs-NEW scenario is still caught; the equivalent-spelling case is
not reported.

**Reporting.** `FieldCheckRow` gained a `detail: str = ""` and the CLI prints the non-empty
ones under the table. A sixth column would have pushed the annotations into wrapping on a
normal terminal for the sake of a usually-empty cell, and would have invalidated the table
the how-to already shows. `test_a_matching_row_carries_no_detail` guards that a clean run
prints none.

`0df674c` lands the dataclass field inert, ahead of the tests, because basedpyright strict
rejects a test naming an attribute that does not exist yet — the same constraint plan 48-03
hit, resolved the same way, without `--no-verify`.

**Verified.** Both review scenarios were red first (`- drift / + match`) and are green now,
plus the false-positive guard described above.

### WR-02: The "no data rows" guard did not wrap the method the zero-row route calls

**Files modified:** `tests/unit/codegen/conftest.py`,
`tests/unit/codegen/test_annotation_check.py`
**Commits:** `f6ca979` (tests), `77e0c6d` (fix)

`fetch_record_batch` is wrapped differently from the other four, exactly as the review
suggested: the call has to succeed because the fallback reads `reader.schema` off it, so the
*reader* is proxied instead. `_GuardedRecordBatchReader` passes `schema` and `close`
through and raises on `read_next_batch`, `read_all`, `read_pandas` and `__iter__`.

The review's second half is done too: `test_the_zero_row_fallback_route_runs_under_the_guard`
monkeypatches `adbc_execute_schema` to raise `NotSupportedError` and drives `probe_schema`
down the fallback branch under the guard, so the branch is now exercised on at least one
backend. Before this, every test using the fixture ran on DuckDB, which answers
`adbc_execute_schema`, and the fallback was never under the guard at all.

**Verified.** `test_the_record_batch_guard_is_not_vacuous` was red first
(`DID NOT RAISE AssertionError`). **Fixing the guard turned no other test red** — the full
suite went from 1307 to 1309, both of them the new ones.

### WR-03: Three setup calls sat outside the `try` that promises a fallback, not a crash

**Files modified:** `src/semolina/codegen/annotation_check.py`,
`tests/unit/codegen/test_annotation_check.py`
**Commits:** `0f6028e` (test), `dc0a5ca` (fix)

`create_builder()`, `_field_groups(...)` and `_canonical_model(view)` moved inside the
`try`, with a comment saying why they belong there.

**The review's example is real but the mechanism is different from what it predicted, and
the difference is worth recording.** The review expected a view with a column named `query`
to shadow `model.query()` and fail at `_build_query`. It never gets that far:
`SemanticViewMeta` has a `RESERVED_FIELD_NAMES` check and raises
`ValueError: Field name 'query' is reserved and cannot be used` inside `_canonical_model`
itself. Measured against the shipped metaclass — `query` and `metrics` raise, while
`_view_name`, `_fields`, `__init__` and `_meta` are all accepted. The conclusion is
unchanged and is if anything stronger: the `ValueError` escaped `check_view`, escaped
`_run_check`'s three narrow `except` clauses (which catch `SemolinaViewNotFoundError`,
`SemolinaConnectionError` and `RuntimeError`), and reached the user as a traceback.

**Verified.** The new test was red with the uncaught `ValueError` from `models.py:121`, and
now returns a `metadata`-routed report whose `probe_error` names the reserved-name problem.

### WR-04: The route label was the last group's, and unprobed rows borrowed one

**Files modified:** `src/semolina/codegen/annotation_check.py`,
`tests/unit/codegen/test_annotation_check.py`
**Commits:** `f91909a` (tests + inert constant), `79dedfa` (fix)

`_probe_view` now returns `list[tuple[pyarrow.Schema, str]]` and `check_view` takes
`field_route` from the pair that resolved the field, so a two-group DuckDB probe answered
by two different routes labels each group correctly. The carried-forward `route` variable is
gone.

Committed-only rows get a new `ROUTE_NOT_PROBED = "not-probed"`. The review offered `ABSENT`
or a new constant; a distinct route constant is the better of the two because `ABSENT` is
already the *annotation* placeholder and reusing it in the route column would make the two
columns say the same word for two different things.

As with WR-01, the constant lands inert alongside the tests (basedpyright strict), which the
commit message states explicitly.

**Verified.** Both defects were red first. The route test monkeypatches `probe_schema` to
relabel the second group's result as `zero-row`, then asserts `revenue` reports
`execute-schema` and `unit_price` reports `zero-row` — with `assert calls["n"] == 2` guarding
the fixture assumption that this view genuinely needs two probes.

### WR-05: Exit code 2's documentation was false in two places

**Files modified:** `src/semolina/cli/__init__.py`, `docs/src/how-to/codegen.rst`
**Commit:** `b4c1b0d`

Both now read "Invalid option -- an unrecognised or omitted `--backend`, or `--check` and
`--model` passed without each other", and the "Both cases mean 'the backend could not be
resolved'" tip is replaced with one that tells you to read stderr for which option it was.
The source comment already required the two to agree; they do.

**This commit also documents the three report changes the other fixes introduced**, which
would otherwise have shipped undocumented:

- a `not-probed` row in the Route table;
- a note that a view needing more than one query gets a route per query;
- a new "Read the Detail lines" subsection covering the role and column comparisons from
  WR-01 and the ambiguous-column case from WR-06, including the point that adding a
  redundant `source=` is not drift.

`@.claude/skills/semolina-docs-author/SKILL.md` was loaded before editing, per CLAUDE.md.
The page is a how-to and stays one: goal-oriented, second person, illustrative snippets, no
new promotional or AI vocabulary, no rule-of-three padding, no em dashes added. `just
docs-build` passes under `-W`, and the page's existing "See also" is untouched.

### WR-06: `_arrow_annotation` treated a duplicate column name as an absent one

**Files modified:** `src/semolina/codegen/annotation_check.py`,
`tests/unit/codegen/test_annotation_check.py`
**Commits:** `205e616` (tests), `6a4513c` (fix)

`get_all_field_indices` replaces `get_field_index`, with the three cases branched
explicitly. `_arrow_annotation` now returns `tuple[str, str] | None` — the annotation paired
with a detail string — so an ambiguous schema can *say so* rather than fall back silently,
which is what the review asked for and what the WR-01 `detail` channel makes possible.

**One judgement call inside this fix.** The ambiguity detail does **not** move the row to
`drift` on its own. `status` is a statement about the *model*, and an ambiguous schema is a
fact about the warehouse; the row reports `Any`, which already drifts against any concrete
committed annotation. So `status` is computed from the annotation plus `model_detail` only,
while `detail` carries both.

**Verified.** Red first with `- execute-schema / + metadata`. The paired test
`test_a_genuinely_absent_column_still_takes_the_metadata_route` confirms the fix did not
collapse the *other* direction: a column the schema truly lacks still routes to metadata.

### IN-01: Encoding-only Arrow types other than `dictionary` fell through to `Any`

**Files modified:** `src/semolina/codegen/arrow_map.py`,
`tests/unit/codegen/test_arrow_map.py`
**Commits:** `5f88ea4` (tests), `652d2e4` (fix)

The recursion was added rather than the docstring amended, because the recursion is
measurably the honest answer. Measured on pyarrow 24.0.0 before deciding:
`pc.run_end_encode(pa.array(["a", "a", "b"]))` in a `RecordBatch` yields
`[{'x': 'a'}, {'x': 'a'}, {'x': 'b'}]` through `to_pylist()` — plain `str`, exactly as a
dictionary column does. Returning `None` would have sent an ordinary string column to a
TODO comment on the strength of how the driver packed it. `pyarrow.types.is_run_end_encoded`
exists at that version and `.value_type` resolves to `string`, both confirmed directly.

The two predicates share one arm, so the "an encoding over an unmapped value type still
returns `None`" property comes for free for both — asserted by
`test_run_end_encoded_of_an_unmapped_value_type_returns_none`.

**Verified.** Red first (`None` where `str` was expected), green after, and the artifact
regenerates byte-identically — no driver in this repo produces REE today, so nothing
measured changed.

### IN-02: The Snowflake cassette path was resolved relative to the cwd

**Files modified:** `tests/unit/codegen/test_annotation_check.py`
**Commit:** `888e189`

`REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]` anchors it, matching
`tests/integration/test_type_fidelity.py`'s idiom. `SNOWFLAKE_PROBE_CASSETTE` is now a
`Path` rather than a bare string, so `_recorded_schema` no longer has to construct one.

**Verified by running the failure the finding predicts.** From `src/` rather than the repo
root: 3 failed before the change, 3 passed after. Same three tests, same command.

## Confirmed, no change required

### IN-03: `tests/type_fidelity_probe.py` may carry imports left behind by the promotion

**Outcome: audited, and there is no residue.** The finding asked for "a deliberate look
rather than trusting F401 alone", which is what it got — and the answer is that the module
is clean.

The two the review named specifically are both still load-bearing after `ProbeResult` and
`probe_schema` moved to `src/`:

| Import | Consumers |
|---|---|
| `dataclass` | four surviving `@dataclass(frozen=True)` decorators (lines 397, 840, 867, 1479) |
| `pyarrow` | `_read_cassette_table`'s return annotation (1032) and `pyarrow.ipc.open_file` (1045) |

Every other header import was checked the same way rather than only those two. The eight
that occur exactly twice — `argparse`, `difflib`, `textwrap`, `tomllib`, `importlib`,
`SemanticView`, `ROUTE_EXECUTE_SCHEMA`, `Mapping` — were each opened and confirmed to have a
real call site (`argparse.ArgumentParser` at 1922, `difflib.unified_diff` at 1951,
`textwrap.wrap` at 1303, `tomllib.load` at 977, `importlib.util.find_spec` at 1586,
`class TypeFidelityView(SemanticView, ...)` at 140, the route comparison at 1732,
`Mapping[str, DownstreamObservation]` at 1638). Nothing to drop.

This is recorded as "confirmed" rather than "skipped": the work the finding asked for was
done, and finding nothing is the result, not an omission.

## Notes for the orchestrator

**Three findings turned out to have small errors in their suggested fixes**, all recorded
above with evidence rather than quietly worked around:

- **WR-01's snippet compares raw `source=` overrides**, which reports drift for the
  hand-written `source=` the how-to documents. Comparing the resolved column name instead
  catches the same real drift without the false positive.
- **WR-03's predicted mechanism is wrong** (the failure is `SemanticViewMeta`'s reserved-name
  check, not `model.query()` shadowing). The finding is still correct; only the explanation
  moves.
- **CR-01/CR-02/CR-03's suggested assertions** would have passed vacuously or failed
  spuriously on substring counts. The tests assert on parsed structure instead — stripped
  SQL literals for CR-02, `ast.parse` for CR-03, explicit ANSI codes for CR-01.

**Nothing was dismissed.** All twelve findings held up.

**Two behaviour changes are worth a line in the phase summary**, because they are visible to
anyone who has already scripted against `--check`:

1. `--check` now reports drift for a changed field role or a changed resolved column, not
   only for a changed annotation. A model that passed before can fail now, correctly.
2. A field the warehouse does not have is labelled `not-probed` rather than borrowing the
   probe's route.

Both are documented in `docs/src/how-to/codegen.rst` as of `b4c1b0d`.

---

_Fixed: 2026-08-12_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
