---
phase: quick-11
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/conftest.py
autonomous: true
requirements:
  - CI-ANSI-FIX

must_haves:
  truths:
    - "CI test run passes with GITHUB_ACTIONS=true set in environment"
    - "test_help_shows_usage asserts on plain '--backend' not ANSI-decorated string"
    - "All 739 tests pass under simulated CI conditions"
  artifacts:
    - path: "tests/conftest.py"
      provides: "pytest_configure hook that sets _TYPER_FORCE_DISABLE_TERMINAL=1 before any test module imports Typer"
      contains: "_TYPER_FORCE_DISABLE_TERMINAL"
  key_links:
    - from: "tests/conftest.py (pytest_configure)"
      to: "typer.rich_utils.FORCE_TERMINAL"
      via: "_TYPER_FORCE_DISABLE_TERMINAL env var read at Typer import time"
      pattern: "_TYPER_FORCE_DISABLE_TERMINAL"
---

<objective>
Commit the working-tree fix in tests/conftest.py that prevents Typer from emitting
ANSI escape codes in CI test output when GITHUB_ACTIONS=true is set.

Purpose: CI was failing because Typer's rich_utils.py reads GITHUB_ACTIONS at import
time and bakes FORCE_TERMINAL=True into a module-level constant, causing Rich Console
to emit ANSI codes even when NO_COLOR=1 is set. The fix adds _TYPER_FORCE_DISABLE_TERMINAL=1
to the pytest_configure hook, which Typer reads at import time to override FORCE_TERMINAL
back to False.

Output: A single commit with the conftest.py change and all quality gates passing.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Run quality gates and commit the conftest.py fix</name>
  <files>tests/conftest.py</files>
  <action>
    The fix is already applied to the working tree. tests/conftest.py has a
    pytest_configure hook that calls:

      os.environ.setdefault("_TYPER_FORCE_DISABLE_TERMINAL", "1")
      os.environ.setdefault("NO_COLOR", "1")

    Run all quality gates in order:
      1. uv run ruff check
      2. uv run ruff format --check
      3. uv run basedpyright
      4. GITHUB_ACTIONS=true uv run --extra dev pytest tests/ -n auto --snapshot-warn-unused -q

    If any gate fails, fix the issue before proceeding. Format issues: apply with
    `uv run ruff format tests/conftest.py`.

    Once all gates pass, commit ONLY tests/conftest.py:
      git add tests/conftest.py
      git commit -m "fix(tests): set _TYPER_FORCE_DISABLE_TERMINAL in pytest_configure to suppress ANSI codes in CI"

    Do NOT amend any previous commit.
  </action>
  <verify>
    <automated>GITHUB_ACTIONS=true uv run --extra dev pytest tests/unit/codegen/test_cli.py::TestCLIBasicBehavior::test_help_shows_usage -v 2>&1 | tail -5</automated>
  </verify>
  <done>
    All quality gates pass (ruff check, ruff format --check, basedpyright, pytest 739 passed).
    git log --oneline -1 shows the new commit for conftest.py.
    test_help_shows_usage passes with GITHUB_ACTIONS=true.
  </done>
</task>

</tasks>

<verification>
Confirm ANSI suppression works under simulated CI:

  GITHUB_ACTIONS=true uv run --extra dev pytest tests/ -n auto --snapshot-warn-unused -q

All 739 tests pass. No ANSI assertion failures in test_cli.py.
</verification>

<success_criteria>
- ruff check: 0 errors
- ruff format --check: no changes needed
- basedpyright: 0 errors
- pytest (GITHUB_ACTIONS=true): 739 passed, 0 failed
- git log: new commit present for tests/conftest.py
</success_criteria>

<output>
After completion, create `.planning/quick/11-fix-ci-test-failures/quick-11-01-SUMMARY.md`
with what was done, the commit hash, and verification results.
</output>
