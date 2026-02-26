---
status: complete
phase: 10-documentation
source: 10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md, 10-04-SUMMARY.md
started: 2026-02-19T22:00:00Z
updated: 2026-02-19T22:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Docs Build (mkdocs build --strict)
expected: Running `mkdocs build --strict` completes with exit code 0 and no warnings. The site/ directory is created.
result: issue
reported: "WARNING - A reference to 'reference' is included in the 'nav' configuration, which is not found in the documentation files."
severity: major
fix_applied: "gen_ref_pages.py had `if __name__ == '__main__': main()` guard — runpy.run_path() sets __name__ to '<run_path>' not '__main__', so main() was never called. Removed the guard; main() now calls unconditionally. Build passes exit 0."

### 2. Doctests Pass
expected: Running `uv run pytest src/ --doctest-modules -v` collects doctest items from cubano source modules and all pass (no failures). You should see items like `cubano.query.Query.execute`, `cubano.fields.Field.asc`, etc.
result: pass

### 3. Docs Serve — Landing Page
expected: Running `mkdocs serve` starts a local server at http://127.0.0.1:8000. The landing page loads with a card grid linking to Getting Started, Models, Queries, and API Reference sections. Dark/light mode toggle is visible in the top bar.
result: pass

### 4. Getting Started Guide — First Query Example
expected: Browsing to http://127.0.0.1:8000/guides/first-query/ shows a guide that uses the model-centric API: `Model.query().metrics(...).execute()` (not the old `Query()` constructor). The example runs to completion without errors if followed.
result: pass

### 5. Filtering Guide
expected: Browsing to http://127.0.0.1:8000/guides/filtering/ shows Q-object filter examples using `.where(Q(...))` syntax. The 9 lookup expressions (gt, gte, lt, lte, contains, startswith, endswith, in, isnull) are documented with code examples.
result: pass

### 6. API Reference — Auto-Generated Modules
expected: Browsing to http://127.0.0.1:8000/api/ (or clicking "API Reference" in the nav) shows auto-generated reference pages for cubano modules (fields, filters, models, query, results, registry, etc.) with docstrings rendered as formatted HTML.
result: pass

### 7. GitHub Actions Docs Workflow
expected: `.github/workflows/docs.yml` exists and is configured to trigger on push to main. It has two jobs: a build job (runs `mkdocs build --strict`) and a deploy job (uses `actions/deploy-pages`). No `contents: write` permission — only `pages: write` and `id-token: write`.
result: pass

## Summary

total: 7
passed: 6
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "mkdocs build --strict exits 0 with no warnings"
  status: failed
  reason: "User reported: WARNING - A reference to 'reference' is included in the 'nav' configuration, which is not found in the documentation files."
  severity: major
  test: 1
  root_cause: "gen_ref_pages.py wrapped main() call in `if __name__ == '__main__'` guard — runpy.run_path() (used by mkdocs-gen-files plugin) sets __name__ to '<run_path>', not '__main__', so main() was never invoked and the reference/ virtual directory was never generated"
  artifacts:
    - path: "docs/scripts/gen_ref_pages.py"
      issue: "if __name__ == '__main__' guard prevented main() from running via runpy.run_path()"
  missing:
    - "Call main() unconditionally at module level"
  fix_applied: true
