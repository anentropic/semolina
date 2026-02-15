---
phase: quick-01
plan: 1
type: execute
wave: 1
depends_on: []
autonomous: true
files_modified:
  - .planning/research/CONVENTIONS.md
must_haves:
  truths:
    - "Future contributors can reference documented typing and annotation conventions"
    - "Code style preferences are captured in a canonical location"
  artifacts:
    - path: ".planning/research/CONVENTIONS.md"
      provides: "Typing and code style conventions"
      contains: "Final, ClassVar, type annotation strategy"
  key_links: []
---

<objective>
Document code style and typing conventions for the Cubano project.

Purpose: Capture current code style preferences in a canonical location so future work (both human and Claude) follows consistent patterns.

Output: CONVENTIONS.md in .planning/research/ documenting typing conventions, import patterns, and code style decisions.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@pyproject.toml
</context>

<tasks>

<task type="auto">
  <name>Create CONVENTIONS.md documenting typing and code style</name>
  <files>.planning/research/CONVENTIONS.md</files>
  <action>
Create .planning/research/CONVENTIONS.md documenting:

**Typing Conventions:**
- No `from __future__ import annotations` unless necessary (3.11+ has native support)
- Mark all constants with `Final` type (from typing module)
- Mark all class attributes with `ClassVar` where not modified by instances
- Function parameters: permissive types (e.g., `Iterable` over `list`) for flexibility
- Function returns: precise types (e.g., `list[str]` not `Iterable[str]`) for clarity
- Prefer specific type annotations over `Any` where possible (use `Any` only when needed)

**Import Patterns:**
- `TYPE_CHECKING` imports for type-only dependencies to avoid circular imports
- Alphabetical import sorting (ruff isort I rules)

**Code Style:**
- Line length: 100 characters (enforced by ruff)
- Multi-line docstrings: opening/closing `"""` on own lines
- D213 enforced: summary on second line after opening quotes
- Minimal `# type: ignore` in code; prefer pyproject.toml-level exemptions

**Quality Gates:**
- Typecheck: `uv run basedpyright` (strict mode)
- Lint: `uv run ruff check`
- Format: `uv run ruff format --check` (apply with `uv run ruff format`)
- Tests: `uv run --extra dev pytest`

Reference existing code in src/cubano/ for examples of Final, ClassVar usage.
  </action>
  <verify>
File exists at .planning/research/CONVENTIONS.md
Contains sections on typing conventions, import patterns, code style, and quality gates
References Final, ClassVar, TYPE_CHECKING patterns
  </verify>
  <done>
CONVENTIONS.md exists and documents all typing/style preferences listed above with examples from the codebase
  </done>
</task>

</tasks>

<verification>
Read .planning/research/CONVENTIONS.md and verify all conventions are documented clearly with rationale.
</verification>

<success_criteria>
- [ ] .planning/research/CONVENTIONS.md exists
- [ ] Documents typing conventions (Final, ClassVar, permissive params, precise returns)
- [ ] Documents import patterns (TYPE_CHECKING)
- [ ] Documents code style (line length, docstrings, D213)
- [ ] Documents quality gates (basedpyright, ruff, pytest)
- [ ] Provides clear examples and rationale
</success_criteria>

<output>
After completion, create `.planning/quick/1-capture-and-document-code-style-preferen/1-SUMMARY.md`
</output>
