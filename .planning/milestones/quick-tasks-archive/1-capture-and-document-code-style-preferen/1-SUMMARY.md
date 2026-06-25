---
phase: quick-01
plan: 1
subsystem: documentation
tags: [conventions, typing, code-style, quality-gates]
dependency_graph:
  requires: []
  provides:
    - Typing conventions (Final, ClassVar, permissive params, precise returns)
    - Import patterns (TYPE_CHECKING for circular dependencies)
    - Code style guidelines (line length, docstrings, D213)
    - Quality gate commands (basedpyright, ruff, pytest)
  affects: [all-future-development]
tech_stack:
  added: []
  patterns: [typing-conventions, import-patterns, quality-gates]
key_files:
  created:
    - .planning/research/CONVENTIONS.md
  modified: []
decisions:
  - "No future annotations unless needed for circular imports (Python 3.11+ has native support)"
  - "Final for constants, ClassVar for class attributes"
  - "Permissive parameter types (Iterable), precise return types (list)"
  - "TYPE_CHECKING imports for type-only dependencies"
  - "Minimize type: ignore comments, prefer pyproject.toml exemptions"
metrics:
  duration: 1.96 min
  tasks: 1
  commits: 1
  files_created: 1
  files_modified: 0
  completed: 2026-02-15
---

# Quick Task 1: Code Style Conventions Summary

**One-liner:** Documented typing conventions (Final/ClassVar), import patterns (TYPE_CHECKING), code style (D213 docstrings), and quality gates for consistent Cubano development.

---

## Overview

Created comprehensive code conventions documentation in `.planning/research/CONVENTIONS.md` to guide future development. The document captures typing preferences, import strategies, code style rules, and quality gate requirements.

**Key achievement:** Centralized reference for all code style decisions, ensuring consistency across human and Claude Code contributions.

---

## What Was Built

### 1. Typing Conventions

**Final for Constants:**
- Mark all module-level constants with `Final[T]`
- Makes immutability intent explicit
- Type checkers can enforce

**ClassVar for Class Attributes:**
- Mark class-level attributes with `ClassVar[T]`
- Distinguishes class vs instance attributes
- Prevents accidental shadowing

**Function Annotations Strategy:**
- Parameters: permissive types (Iterable, Mapping) for flexibility
- Returns: precise types (list, dict) for caller clarity
- Avoids `Any` except for duck typing or circular import workarounds

**Current codebase examples documented:**
- `registry._default_name` should be `Final[str]`
- `SemanticView._view_name`, `_fields`, `_frozen` should use `ClassVar`
- `query.py` uses `Any` for parameters with runtime validation

### 2. Import Patterns

**TYPE_CHECKING for Circular Dependencies:**
- Import type-only dependencies under `if TYPE_CHECKING:`
- Requires `from __future__ import annotations`
- Used in `engines/base.py` to import Query

**Import Sorting:**
- Automated via ruff isort (I rules)
- Standard library → third-party → local, alphabetically sorted

### 3. Code Style

**Line Length:**
- 100 characters maximum (configured in pyproject.toml)
- Enforced by ruff formatter

**Docstrings:**
- Multi-line: opening/closing `"""` on own lines
- D213: summary on second line after opening quotes
- Matches Google/NumPy conventions

**Type Ignore Comments:**
- Minimize inline comments
- Prefer pyproject.toml-level exemptions
- Only use when issue is line-specific

### 4. Quality Gates

**Commands documented:**
- `uv run basedpyright` - strict mode type checking
- `uv run ruff check` - linting (with --fix for auto-fixes)
- `uv run ruff format --check` - formatting check (uv run ruff format to apply)
- `uv run --extra dev pytest` - test execution

**All must pass before committing.**

### 5. Practical Examples

**Included real examples from codebase:**
- TYPE_CHECKING pattern from `engines/base.py`
- Permissive params/precise returns from `query.py`
- Docstring format (D213) from `results.py`

**Future work section:**
- Add Final to registry constants
- Add ClassVar to model class attributes
- Review Any usage for Protocol types
- Audit type: ignore comments

---

## Verification

**File exists:**
```bash
ls -la /Users/paul/Documents/Dev/Personal/cubano/.planning/research/CONVENTIONS.md
```
Output: 470 lines documenting conventions

**Content verification:**
- Typing conventions section: Final, ClassVar, permissive params, precise returns, avoid Any
- Import patterns section: TYPE_CHECKING, import sorting
- Code style section: line length, docstrings (D213), minimal type: ignore
- Quality gates section: basedpyright, ruff check, ruff format, pytest
- Examples from codebase: engines/base.py, query.py, results.py
- Checklist for new code
- Future work section

All success criteria met.

---

## Deviations from Plan

None - plan executed exactly as written.

---

## Commits

| Task | Name                                   | Commit  | Files                                   |
| ---- | -------------------------------------- | ------- | --------------------------------------- |
| 1    | Create CONVENTIONS.md                  | 495a751 | .planning/research/CONVENTIONS.md       |

---

## Impact

**Documentation:**
- Central reference for typing conventions
- Import strategy for circular dependencies
- Code style enforcement guidelines
- Quality gate definitions

**Future development:**
- Consistent typing across all new code
- Clear guidance for Final/ClassVar usage
- TYPE_CHECKING pattern established
- Quality gate commands documented

**Stakeholders:**
- Future contributors (human and Claude)
- Code reviewers
- Maintainers ensuring consistency

---

## Self-Check: PASSED

**Files created:**
```bash
[ -f "/Users/paul/Documents/Dev/Personal/cubano/.planning/research/CONVENTIONS.md" ] && echo "FOUND" || echo "MISSING"
```
Output: FOUND

**Commit exists:**
```bash
git log --oneline --all | grep -q "495a751" && echo "FOUND" || echo "MISSING"
```
Output: FOUND

**Content verification:**
- Contains typing conventions (Final, ClassVar, permissive params, precise returns)
- Contains import patterns (TYPE_CHECKING)
- Contains code style (D213, line length, minimal type: ignore)
- Contains quality gates (basedpyright, ruff, pytest)
- Contains examples from codebase
- Contains checklist for new code
- Contains future work section

All verifications passed.
