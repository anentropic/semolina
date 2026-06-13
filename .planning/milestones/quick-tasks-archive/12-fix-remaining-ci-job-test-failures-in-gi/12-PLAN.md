---
phase: quick-12
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/ci.yml
autonomous: true
requirements: []

must_haves:
  truths:
    - "CI passes without Snowflake credentials"
    - "The jaffle-shop test step runs only mock-marked tests"
    - "Warehouse tests are not attempted in CI"
  artifacts:
    - path: ".github/workflows/ci.yml"
      provides: "CI workflow definition"
      contains: 'uv run pytest -m "mock" -v'
  key_links:
    - from: ".github/workflows/ci.yml"
      to: "cubano-jaffle-shop test suite"
      via: "pytest -m mock filter"
      pattern: 'pytest -m "mock" -v'
---

<objective>
Remove warehouse-marked tests from the CI jaffle-shop test step. Warehouse tests require live Snowflake credentials that are not available in GitHub Actions, causing 15 test failures. Filtering to `mock` only keeps the 13 passing mock tests and eliminates the credential-driven failures.

Purpose: Unblock CI green on every push without real warehouse credentials.
Output: Updated `.github/workflows/ci.yml` with corrected pytest marker filter.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.github/workflows/ci.yml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Restrict jaffle-shop CI step to mock tests only</name>
  <files>.github/workflows/ci.yml</files>
  <action>
    On line 118 of `.github/workflows/ci.yml`, change:

        uv run pytest -m "mock or warehouse" -v

    to:

        uv run pytest -m "mock" -v

    No other changes. The `warehouse` marker requires live Snowflake credentials
    (SNOWFLAKE_USER, SNOWFLAKE_ACCOUNT, etc.) which are empty strings in CI,
    causing immediate "User is empty" failures on all 15 warehouse tests.
    Mock tests have no credential dependency and must remain in CI.
  </action>
  <verify>
    grep 'pytest -m "mock" -v' /Users/paul/Documents/Dev/Personal/cubano/.github/workflows/ci.yml
  </verify>
  <done>
    Line 118 reads `uv run pytest -m "mock" -v` with no mention of `warehouse`.
    The grep above returns exactly one match.
  </done>
</task>

</tasks>

<verification>
Confirm the change is correct and complete:

```
grep -n 'pytest.*jaffle\|mock\|warehouse' /Users/paul/Documents/Dev/Personal/cubano/.github/workflows/ci.yml
```

Expected: the jaffle-shop step shows `-m "mock"` only. No `warehouse` marker remains in that step.

Note: ruff check / ruff format are Python-only tools and do not apply to YAML files. No additional quality gates required for this single-line YAML change.
</verification>

<success_criteria>
- `.github/workflows/ci.yml` line 118 contains `uv run pytest -m "mock" -v`
- No reference to `warehouse` marker in the jaffle-shop test step
- CI job will run 13 mock tests and skip all 15 warehouse tests
- Change committed to git
</success_criteria>

<output>
After completion, create `.planning/quick/12-fix-remaining-ci-job-test-failures-in-gi/12-SUMMARY.md`
</output>
