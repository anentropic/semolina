---
phase: quick-10
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/cubano/engines/databricks.py
  - src/cubano/engines/snowflake.py
  - src/cubano/engines/mock.py
  - src/cubano/engines/sql.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "API reference renders `# comment` lines as code, not markdown headings"
    - "`uv run mkdocs build --strict` passes with no warnings"
  artifacts:
    - path: "src/cubano/engines/databricks.py"
      provides: "to_sql Example: section wrapped in fenced code block"
    - path: "src/cubano/engines/snowflake.py"
      provides: "to_sql Example: section wrapped in fenced code block"
    - path: "src/cubano/engines/mock.py"
      provides: "class-level and to_sql Example: sections wrapped in fenced code blocks"
    - path: "src/cubano/engines/sql.py"
      provides: "SQLBuilder class Example: section wrapped in fenced code block"
  key_links:
    - from: "docstring Example: sections"
      to: "mkdocstrings HTML output"
      via: "fenced python code block prevents markdown heading interpretation"
      pattern: "```python"
---

<objective>
Fix five `Example:` sections in engine docstrings where Python `# comment` lines render as markdown headings in the API reference.

Purpose: mkdocstrings renders `Example:` section content as markdown. Lines starting with `#` become headings (h1 scaled to h5 in context). Wrapping the content in a fenced ` ```python ``` ` block forces syntax highlighting and prevents heading interpretation.
Output: Four engine source files with corrected docstrings. `uv run mkdocs build --strict` passes.
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
  <name>Task 1: Wrap Example: sections in fenced code blocks</name>
  <files>
    src/cubano/engines/databricks.py
    src/cubano/engines/snowflake.py
    src/cubano/engines/mock.py
    src/cubano/engines/sql.py
  </files>
  <action>
    In each file, find every `Example:` section that contains bare `# comment` lines and
    wrap the entire body of that section in a fenced ` ```python ``` ` block.

    The pattern to fix is:

    ```
    Example:
        some_code = here()
        # This comment line renders as a heading
        # Another heading line
    ```

    Change to:

    ```
    Example:
        ```python
        some_code = here()
        # This comment line stays as a comment
        # Another comment line
        ```
    ```

    IMPORTANT: The fenced block must be indented at the same level as the surrounding
    docstring content (4 spaces inside the docstring). Each ` ``` ` delimiter line gets
    the same 4-space indent as the code lines.

    Specific locations to fix (all confirmed via grep):

    **src/cubano/engines/databricks.py** lines 144-149 (`to_sql` method):
    - Wrap lines 145-149 (the `sql = engine.to_sql(query)` through `# GROUP BY ALL` block)
      in ` ```python ``` `

    **src/cubano/engines/snowflake.py** lines 145-150 (`to_sql` method):
    - Wrap lines 146-150 (the `sql = engine.to_sql(query)` through `# GROUP BY ALL` block)
      in ` ```python ``` `

    **src/cubano/engines/mock.py** — two locations:
    1. Lines 29-53 (class-level `MockEngine` docstring `Example:` section):
       - Wrap lines 30-53 (from `from cubano import ...` through the closing
         `# GROUP BY ALL` comment inside `test_query`) in ` ```python ``` `
    2. Lines 100-104 (`to_sql` method `Example:` section):
       - Wrap lines 101-104 (the `sql = engine.to_sql(query)` through `# GROUP BY ALL`
         block) in ` ```python ``` `

    **src/cubano/engines/sql.py** lines 340-357 (`SQLBuilder` class `Example:` section):
    - Wrap lines 341-357 (the `from cubano import ...` through `# LIMIT 100` block)
      in ` ```python ``` `

    Do NOT change any `Returns:` sections — inline SQL examples without `#` prefixes
    are not affected.

    After editing, run the quality gates:
    1. `uv run ruff format src/cubano/engines/` — auto-format (docstring changes are
       unlikely to affect formatting but run as a precaution)
    2. `uv run ruff check src/cubano/engines/` — lint
    3. `uv run basedpyright` — typecheck
    4. `uv run --extra dev pytest` — tests (docstring changes should not break tests)
    5. `uv run mkdocs build --strict` — verify docs render cleanly
  </action>
  <verify>
    <automated>uv run mkdocs build --strict</automated>
    <manual>
      Open docs/site/reference/engines/index.html (or serve with `uv run mkdocs serve`)
      and confirm that the `Example:` code blocks in MockEngine, SnowflakeEngine,
      DatabricksEngine, and SQLBuilder render as syntax-highlighted code, not as headings.
    </manual>
  </verify>
  <done>
    `uv run mkdocs build --strict` exits 0 with no warnings.
    All four quality gates (ruff format, ruff check, basedpyright, pytest) pass.
    The five affected `Example:` sections each contain a fenced ` ```python ``` ` block.
  </done>
</task>

</tasks>

<verification>
Run all quality gates in order:
1. `uv run ruff format --check` — no formatting drift
2. `uv run ruff check` — no lint errors
3. `uv run basedpyright` — 0 type errors
4. `uv run --extra dev pytest` — all tests pass
5. `uv run mkdocs build --strict` — docs build cleanly
</verification>

<success_criteria>
- `uv run mkdocs build --strict` passes with exit code 0
- No new lint, typecheck, or test failures introduced
- All five `Example:` sections in engine docstrings wrap their content in ` ```python ``` ` fenced blocks
</success_criteria>

<output>
After completion, create `.planning/quick/10-fix-docstring-examples-in-reference-api-/10-SUMMARY.md`
</output>
