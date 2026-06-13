---
phase: quick-13
plan: 01
subsystem: project-wide
tags: [rename, refactor, packaging]
key-files:
  created: []
  modified:
    - src/semolina/ (was src/cubano/)
    - semolina-jaffle-shop/ (was cubano-jaffle-shop/)
    - semolina-jaffle-shop/src/semolina_jaffle_shop/ (was cubano_jaffle_shop/)
    - docs/src/reference/semolina/ (was docs/src/reference/cubano/)
    - .claude/skills/semolina-docs-author/ (was cubano-docs-author/)
    - pyproject.toml
    - mkdocs.yml
    - CLAUDE.md
    - .github/workflows/ci.yml
    - src/semolina/codegen/templates/python_model.py.jinja2
    - uv.lock
decisions:
  - jinja2 templates not covered by sed passes (extension not in find pattern) - fixed manually
metrics:
  completed: 2026-02-27
---

# Quick Task 13: Rename Project from Cubano to Semolina - Summary

**One-liner:** Full project rename from "cubano" to "semolina" across all directories, Python package, CLI entry point, imports, exception classes, config files, docs, and example project — all quality gates passing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rename directories with git mv | 440945a | src/semolina/, semolina-jaffle-shop/, docs/src/reference/semolina/ |
| 2 | Bulk text replacement (cubano -> semolina) | 62931ed | 96 files across all .py/.toml/.yml/.md |
| 3 | Run quality gates and fix issues | 1a6930e | python_model.py.jinja2 |

## Verification

All quality gates pass:

- **basedpyright:** 0 errors, 0 warnings
- **ruff check:** All checks passed
- **ruff format:** 55 files already formatted
- **pytest (tests/):** 739 passed
- **pytest (src/ doctests):** 20 passed, 16 skipped
- **mkdocs build --strict:** Documentation built successfully

Additional verification:
- `import semolina` works, version `0.1.0`
- `semolina --help` shows CLI working
- No remaining `cubano` references in src/ or tests/

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Jinja2 template not covered by sed passes**
- **Found during:** Task 3 (pytest failure)
- **Issue:** `src/semolina/codegen/templates/python_model.py.jinja2` had `.jinja2` extension which was not included in the `find` pattern (`*.py` / `*.toml` / `*.yml` / `*.yaml` / `*.md`). Template still generated `from cubano import ...` in codegen output.
- **Fix:** Updated template line 7 from `from cubano import` to `from semolina import`
- **Files modified:** `src/semolina/codegen/templates/python_model.py.jinja2`
- **Commit:** 1a6930e

**2. [Rule 2 - Missing] Python package module inside jaffle-shop not renamed**
- **Found during:** Task 2 (inspection)
- **Issue:** `semolina-jaffle-shop/src/cubano_jaffle_shop/` directory was not renamed by `git mv` (only the parent `semolina-jaffle-shop/` was renamed). Tests already imported from `semolina_jaffle_shop` (sed updated imports) but directory name was still `cubano_jaffle_shop`.
- **Fix:** `git mv` to rename from `cubano_jaffle_shop` to `semolina_jaffle_shop`
- **Files modified:** 3 Python files in `semolina-jaffle-shop/src/semolina_jaffle_shop/`
- **Commit:** 62931ed

**3. [Rule 2 - Missing] `.claude/skills/cubano-docs-author/` not renamed**
- **Found during:** Task 2 (inspection of CLAUDE.md after sed)
- **Issue:** CLAUDE.md was updated to reference `@.claude/skills/semolina-docs-author/SKILL.md` but the skill directory was still named `cubano-docs-author`. This would break any agent loading the skill.
- **Fix:** `git mv` to rename the skill directory
- **Files modified:** `.claude/skills/semolina-docs-author/SKILL.md`
- **Commit:** 62931ed

**4. [Rule 3 - Blocking] uv.lock still referenced old package name**
- **Found during:** Task 2 (inspection)
- **Issue:** uv.lock had `cubano` and `cubano-jaffle-shop` entries even after pyproject.toml was updated.
- **Fix:** Ran `uv lock` to regenerate the lock file
- **Files modified:** `uv.lock`
- **Commit:** 62931ed

## Success Criteria Verification

- [x] `src/semolina/` exists, `src/cubano/` does not
- [x] `semolina-jaffle-shop/` exists, `cubano-jaffle-shop/` does not
- [x] `pyproject.toml` name = "semolina", CLI entry = `semolina = "semolina.cli:app"`
- [x] Exception classes: `SemolinaConnectionError`, `SemolinaViewNotFoundError`
- [x] Zero remaining "cubano" references in source, tests, config (excluding CHANGELOG and git history)
- [x] All quality gates pass: basedpyright (0 errors), ruff check (clean), ruff format (clean), pytest (739 passed), mkdocs build --strict (success)

## Self-Check: PASSED

Files verified:
- `/Users/paul/Documents/Dev/Personal/cubano/src/semolina/__init__.py` - EXISTS
- `/Users/paul/Documents/Dev/Personal/cubano/semolina-jaffle-shop/pyproject.toml` - EXISTS
- `/Users/paul/Documents/Dev/Personal/cubano/src/semolina/codegen/templates/python_model.py.jinja2` - EXISTS (contains `from semolina import`)

Commits verified:
- `440945a` - chore(quick-13): rename directories with git mv
- `62931ed` - chore(quick-13): bulk rename cubano -> semolina
- `1a6930e` - fix(quick-13): update jinja2 template import from cubano to semolina
