# Semolina

Semolina is "the ORM for your Semantic Layer".

Semolina is an ultramodern, strongly-typed, Pythonic library for querying data warehouse semantic views - Snowflake 'semantic views' and Databricks 'metric views'. Python >=3.11, built with uv.

## Quality gates

Run all four before committing:

- **Typecheck:** `uv run basedpyright` (strict mode, configured in pyproject.toml)
- **Lint:** `uv run ruff check`
- **Format:** `uv run ruff format --check` (apply with `uv run ruff format`)
- **Tests:** `uv run --extra dev pytest`
- **Docs build:** `uv run sphinx-build -W docs/src docs/_build`

Avoid `# type: ignore` in code; prefer solving the typing issue, use pyproject.toml-level exemptions as last resort.

## Documentation standards

### Mandatory skill

When writing or modifying documentation, you MUST load:

```
@.claude/skills/semolina-docs-author/SKILL.md
```

This skill packages Diataxis classification, Semolina audience/voice, and the humanizer pass in one place. It references the per-type Diataxis reference files on demand.

### When to apply

- **New pages:** full workflow (mandatory)
- **Major rewrites (>50% of page changed):** full workflow (mandatory)
- **Minor fixes (typos, version numbers, small corrections):** not required
- **API surface changes:** update corresponding docs (mandatory), full rewrite not required

### GSD planner instruction

For any PLAN.md that includes documentation tasks, add to its `<execution_context>` block:

```
@.claude/skills/semolina-docs-author/SKILL.md
```

### Content types

- **Tutorials** (`docs/src/tutorials/`): Runnable code with imports and expected output
  shown. Learning-oriented, guided step-by-step.
- **How-to guides** (`docs/src/how-to/`): Illustrative snippets showing key concepts.
  Goal-oriented, reader supplies setup. Use sphinx-design tab-set with
  `:sync-group: warehouse` for SQL dialect examples.
- **Reference** (`docs/src/reference/`): Auto-generated via sphinx-autoapi. Do not
  hand-write API docs.
- **Explanation** (`docs/src/explanation/`): Background concepts, no step-by-step
  instructions. Link to tutorials/how-tos for action items.

### Writing voice

- **Audience:** Data/analytics engineers comfortable with SQL and Python
  - They likely already have a 'Semantic Layer' set up in their data warehouse
  - Looking for a library to help them build out the app backend for their BI reporting dashboard service
- **Tone:** Warm but efficient (like FastAPI/Stripe docs)
- **Perspective:** Second person ("you")
- **Pages:** Self-contained with "See also" links at bottom for cross-referencing

## Bug fixes

When fixing a bug, always reproduce it first with a failing test case before implementing the fix. Place the test adjacent to the most similar existing tests. The commit sequence should be: failing test first, then the fix that makes it pass.

## Code style

- Line length: 100 chars
- Docstrings: opening/closing `"""` on own lines for multi-line docstrings
- Import sorting: ruff isort (I rules) enabled
- D213 enforced (summary on second line after opening quotes)

### Docstring examples (Google style)

`Example:` section content is rendered by sphinx-autoapi with napoleon. Use a `.. code-block:: python` RST directive (not markdown fenced blocks — triple backticks render as literal text):

```text
Example:
    .. code-block:: python

        result = my_function(arg)
        # this comment stays a comment, not a heading
```

Multi-line `Returns:` descriptions are safe — napoleon parses them as a single return value by default.

## Project structure

- Source: `src/semolina/`
- Tests: `tests/`
- Docs: `docs/src/` (Sphinx + shibuya theme with Diataxis tabs)
- Build: uv + pyproject.toml, uv-build backend
