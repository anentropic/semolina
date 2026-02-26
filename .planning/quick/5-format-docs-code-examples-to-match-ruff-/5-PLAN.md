---
phase: quick-5
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/index.md
  - docs/guides/codegen.md
  - docs/guides/filtering.md
  - docs/guides/first-query.md
  - docs/guides/models.md
  - docs/guides/ordering.md
  - docs/guides/queries.md
  - docs/guides/backends/databricks.md
  - docs/guides/backends/overview.md
  - docs/guides/backends/snowflake.md
  - .pre-commit-config.yaml
autonomous: true
requirements: []

must_haves:
  truths:
    - "All Python code blocks in docs pass `uvx blacken-docs --check -l 100` with no rewrites required"
    - "All SQL blocks in docs are readable and consistently formatted (manually verified)"
    - "`mkdocs build --strict` passes with no warnings or errors"
    - "`.pre-commit-config.yaml` has a blacken-docs hook with `-l 100` that runs on `*.md` files"
  artifacts:
    - path: "docs/index.md"
      provides: "Black-formatted Python examples"
    - path: "docs/guides/codegen.md"
      provides: "Black-formatted Python examples"
    - path: "docs/guides/filtering.md"
      provides: "Black-formatted Python examples"
    - path: "docs/guides/first-query.md"
      provides: "Black-formatted Python examples"
    - path: "docs/guides/models.md"
      provides: "Black-formatted Python examples"
    - path: "docs/guides/ordering.md"
      provides: "Black-formatted Python examples"
    - path: "docs/guides/queries.md"
      provides: "Black-formatted Python examples"
    - path: "docs/guides/backends/databricks.md"
      provides: "Black-formatted Python examples"
    - path: "docs/guides/backends/overview.md"
      provides: "Black-formatted Python examples"
    - path: "docs/guides/backends/snowflake.md"
      provides: "Black-formatted Python examples"
  key_links:
    - from: "docs/**/*.md Python blocks"
      to: "ruff format style"
      via: "blacken-docs -l 100 (black-compatible output)"
      pattern: "uvx blacken-docs --check -l 100"
---

<objective>
Format all Python code blocks in the docs to match the project's ruff/black style (100-char line length), and confirm SQL blocks are already clean enough to leave as-is.

Purpose: Docs code examples should look professional and consistent with the project's style. Currently 10 files have Python blocks that need blank-line and argument-formatting fixes (PEP 8 E302 style).
Output: All 10 docs files reformatted in-place, SQL blocks manually verified, MkDocs build clean.
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
  <name>Task 1: Reformat Python blocks with blacken-docs</name>
  <files>
    docs/index.md
    docs/guides/codegen.md
    docs/guides/filtering.md
    docs/guides/first-query.md
    docs/guides/models.md
    docs/guides/ordering.md
    docs/guides/queries.md
    docs/guides/backends/databricks.md
    docs/guides/backends/overview.md
    docs/guides/backends/snowflake.md
  </files>
  <action>
    Run blacken-docs in-place on all 10 affected docs files:

    ```
    uvx blacken-docs -l 100 \
      docs/index.md \
      docs/guides/codegen.md \
      docs/guides/filtering.md \
      docs/guides/first-query.md \
      docs/guides/models.md \
      docs/guides/ordering.md \
      docs/guides/queries.md \
      docs/guides/backends/databricks.md \
      docs/guides/backends/overview.md \
      docs/guides/backends/snowflake.md
    ```

    Typical changes expected: blank lines added between imports and class/function definitions (PEP 8 E302), multi-line function call arguments reflowed to fit 100-char line limit. No semantic changes.

    Do NOT add blacken-docs to pyproject.toml dev/docs groups — it is invoked via `uvx` (ephemeral) and managed by pre-commit after Task 2.
  </action>
  <verify>
    Run check mode to confirm all files now pass:

    ```
    uvx blacken-docs --check -l 100 \
      docs/index.md \
      docs/guides/codegen.md \
      docs/guides/filtering.md \
      docs/guides/first-query.md \
      docs/guides/models.md \
      docs/guides/ordering.md \
      docs/guides/queries.md \
      docs/guides/backends/databricks.md \
      docs/guides/backends/overview.md \
      docs/guides/backends/snowflake.md
    ```

    Expected output: exit 0, no "Requires a rewrite" lines.
  </verify>
  <done>All 10 files report no rewrites needed from blacken-docs --check.</done>
</task>

<task type="auto">
  <name>Task 2: Add blacken-docs pre-commit hook</name>
  <files>
    .pre-commit-config.yaml
  </files>
  <action>
    Add a blacken-docs hook to `.pre-commit-config.yaml` after the ruff-pre-commit block.
    The hook repo is `https://github.com/asottile/blacken-docs`, latest rev should be fetched
    with `pre-commit autoupdate --repo https://github.com/asottile/blacken-docs` after adding,
    or use a known stable rev (check https://github.com/asottile/blacken-docs/releases for latest tag).

    Insert after the shellcheck block:

    ```yaml
      - repo: https://github.com/asottile/blacken-docs
        rev: 1.19.1
        hooks:
          - id: blacken-docs
            args: [-l, "100"]
    ```

    Note: the hook automatically targets `*.md`, `*.rst`, `*.tex` files — no `files:` filter needed.
    After adding, run `pre-commit autoupdate --repo https://github.com/asottile/blacken-docs` to
    ensure the rev is current.
  </action>
  <verify>
    pre-commit run blacken-docs --all-files 2>&1 | tail -5
    # Should show "Passed" for all .md files
  </verify>
  <done>`.pre-commit-config.yaml` has blacken-docs hook; `pre-commit run blacken-docs --all-files` exits 0.</done>
</task>

<task type="auto">
  <name>Task 3: Verify SQL blocks and confirm MkDocs build</name>
  <files></files>
  <action>
    SQL blocks (8 total across all docs) are short SELECT statements and one Snowflake-specific CREATE SEMANTIC VIEW DDL block. sqlfluff is NOT in dev deps and the blocks are already readable. Verify them by reading each file that contains SQL and confirming the blocks look clean — no automated reformatting needed.

    Files likely to contain SQL blocks (based on research): docs/guides/first-query.md, docs/guides/queries.md, docs/guides/filtering.md, docs/guides/ordering.md, docs/guides/backends/snowflake.md.

    After reviewing SQL, run the MkDocs strict build to confirm no broken references or warnings were introduced:

    ```
    uv run --group docs mkdocs build --strict
    ```

    The site/ output directory should build cleanly with exit 0.
  </action>
  <verify>
    1. SQL blocks in docs look consistently formatted (uppercase keywords, consistent indentation).
    2. `uv run --group docs mkdocs build --strict` exits 0 with no warnings.
  </verify>
  <done>SQL blocks are clean (no changes needed), MkDocs strict build passes.</done>
</task>

</tasks>

<verification>
- `uvx blacken-docs --check -l 100 docs/index.md docs/guides/codegen.md docs/guides/filtering.md docs/guides/first-query.md docs/guides/models.md docs/guides/ordering.md docs/guides/queries.md docs/guides/backends/databricks.md docs/guides/backends/overview.md docs/guides/backends/snowflake.md` exits 0
- `pre-commit run blacken-docs --all-files` exits 0
- `uv run --group docs mkdocs build --strict` exits 0
</verification>

<success_criteria>
All Python code examples in docs follow ruff/black style (100-char line length). SQL blocks confirmed clean. MkDocs strict build passes. blacken-docs pre-commit hook installed and passing.
</success_criteria>

<output>
After completion, create `.planning/quick/5-format-docs-code-examples-to-match-ruff-/5-SUMMARY.md`
</output>
