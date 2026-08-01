# Phase 39 — Deferred Items

Items discovered during execution that are out of scope for the current plan
and have been deferred. Per GSD scope boundary rule: only auto-fix issues
DIRECTLY caused by the current task's changes.

## From 39-01

### Pre-existing pyarrow runtime leak via `semolina.config`

**Discovered during:** Task 2 verification of `<acceptance_criteria>` runtime
isolation check `python -c "import semolina.cursor; assert 'pyarrow' not in
sys.modules"`.

**What:** `import semolina.cursor` pulls in `pyarrow` at runtime even with the
new `if TYPE_CHECKING: import pyarrow` block in `cursor.py`.

**Root cause:** Importing `semolina.cursor` triggers `semolina/__init__.py`,
which imports `semolina.config` (for `pool_from_config`), which imports
pyarrow eagerly (likely via `adbc-poolhouse`'s config classes pulling Arrow
schema utilities).

**Evidence:** `cursor.py`'s own AST has zero pyarrow imports at module top
level — only inside `if TYPE_CHECKING:`. Bisection confirmed `semolina.config`
is the entry point that pulls pyarrow into `sys.modules`.

**Why deferred:** Pre-existing condition unrelated to streaming work.
Resolving it requires either:
  1. Lazy-importing `pyarrow` inside `pool_from_config` (or wherever it's
     pulled in), or
  2. Moving the eager import behind a `TYPE_CHECKING` gate in `config.py`
     and accepting any `pyarrow.Schema`/`pyarrow.Table` types declared there
     as forward references.

Both are >50-line refactors that touch a different subsystem than streaming
and risk regressing pool-config codepaths.

**Acceptance impact for 39-01:** The runtime-isolation acceptance criterion
in `39-01-cursor-streaming-impl-PLAN.md` is satisfied at the `cursor.py`
module level (no new pyarrow imports in the streaming code) but cannot be
satisfied at the package level until config.py is fixed.

**Recommended follow-up:** Open a small plan in Phase 40 (or a hotfix) to
lazy-import pyarrow in `semolina.config`. The fix is mechanical once the
pyarrow-using lines are identified.

### Pre-existing codegen import-order test failure

**Discovered during:** Task 2 broader test run (`pytest tests/unit -q`).

**Failing test:** `tests/unit/codegen/test_cli.py::TestReverseCodegenOutput::test_imports_at_top`.

**What:** Test asserts the codegen output contains
`from semolina import Dimension, Fact, Metric, SemanticView` but generator
actually emits `from semolina import SemanticView, Metric, Dimension, Fact`.

**Why deferred:** Failure reproduces on the unmodified branch base
(verified by `git stash` then re-running). Unrelated to STREAM-01/STREAM-02.
Belongs to the codegen subsystem; either the generator should sort imports
or the test assertion should be updated.

**Recommended follow-up:** Track in Phase 40 (codegen polish) where the
codegen output is being refined for v0.5.
