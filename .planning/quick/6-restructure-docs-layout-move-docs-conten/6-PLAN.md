---
phase: quick-6
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/src/  # all 13 markdown files moved here from docs/
  - docs/scripts/gen_ref_pages.py  # moved from scripts/
  - mkdocs.yml
autonomous: true
requirements: []

must_haves:
  truths:
    - "MkDocs finds all markdown source files under docs/src/"
    - "MkDocs uses docs/scripts/gen_ref_pages.py to generate API reference pages"
    - "Edit links on published pages point to the correct GitHub path (docs/src/)"
    - "scripts/ retains only connections.toml files (gen_ref_pages.py is gone)"
    - "mkdocs build --strict passes with zero errors"
  artifacts:
    - path: "docs/src/index.md"
      provides: "Homepage content at new location"
    - path: "docs/src/changelog.md"
      provides: "Changelog content at new location"
    - path: "docs/src/guides/"
      provides: "All guide markdown files at new location"
    - path: "docs/scripts/gen_ref_pages.py"
      provides: "Gen-files script at new location"
    - path: "mkdocs.yml"
      provides: "Updated config pointing to docs/src and docs/scripts"
  key_links:
    - from: "mkdocs.yml"
      to: "docs/src/"
      via: "docs_dir: docs/src"
      pattern: "docs_dir:"
    - from: "mkdocs.yml"
      to: "docs/scripts/gen_ref_pages.py"
      via: "plugins.gen-files.scripts"
      pattern: "docs/scripts/gen_ref_pages\\.py"
    - from: "mkdocs.yml"
      to: "docs/src/ on GitHub"
      via: "edit_uri: edit/main/docs/src/"
      pattern: "edit_uri:"
---

<objective>
Restructure the docs layout by moving all markdown content to docs/src/ and the gen-files script to docs/scripts/, then updating mkdocs.yml to reference the new paths.

Purpose: Clean separation of docs content from scripts; docs/src/ as the canonical docs source directory.
Output: Reorganised docs tree with mkdocs.yml updated; mkdocs build --strict passes.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@mkdocs.yml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Move files with git mv</name>
  <files>
    docs/src/index.md
    docs/src/changelog.md
    docs/src/guides/
    docs/scripts/gen_ref_pages.py
  </files>
  <action>
    Run the following commands in order to create target directories and move files while preserving git history:

    ```
    mkdir -p docs/src docs/scripts
    git mv docs/index.md docs/src/index.md
    git mv docs/changelog.md docs/src/changelog.md
    git mv docs/guides docs/src/guides
    git mv scripts/gen_ref_pages.py docs/scripts/gen_ref_pages.py
    ```

    Do NOT move scripts/connections.toml or scripts/connections.toml.example — those stay in scripts/.
    Do NOT edit gen_ref_pages.py — its internal reference to src/ (Python source) is unrelated to docs/ paths.
  </action>
  <verify>
    Run:
      git status
    Expected: docs/src/index.md, docs/src/changelog.md, docs/src/guides/**, docs/scripts/gen_ref_pages.py shown as renamed. scripts/connections.toml.example unchanged.
  </verify>
  <done>All 13 markdown files are under docs/src/, gen_ref_pages.py is at docs/scripts/gen_ref_pages.py, and scripts/ contains only connections files.</done>
</task>

<task type="auto">
  <name>Task 2: Update mkdocs.yml</name>
  <files>mkdocs.yml</files>
  <action>
    Make three targeted changes to mkdocs.yml:

    1. Add `docs_dir: docs/src` as a top-level key immediately after `edit_uri` (before the `theme:` block). This overrides MkDocs' default of `docs/`.

    2. Update the gen-files script path:
       From: `- scripts/gen_ref_pages.py`
       To:   `- docs/scripts/gen_ref_pages.py`

    3. Update the edit_uri:
       From: `edit_uri: edit/main/docs/`
       To:   `edit_uri: edit/main/docs/src/`

    No other changes to mkdocs.yml.
  </action>
  <verify>
    Run:
      uv run --group docs mkdocs build --strict
    Expected: Build completes with exit code 0, no warnings or errors. Site output written to site/.
  </verify>
  <done>mkdocs build --strict exits 0. docs_dir, scripts path, and edit_uri all reference the new layout.</done>
</task>

</tasks>

<verification>
After both tasks:

1. `git status` shows renames for all 13 .md files and gen_ref_pages.py, plus modification of mkdocs.yml — no untracked docs files left in the old locations.
2. `uv run --group docs mkdocs build --strict` exits 0 with no errors.
3. `ls docs/` shows only `src/` and `scripts/` subdirectories (no loose .md files, no guides/).
4. `ls scripts/` shows only connections.toml files (gen_ref_pages.py is gone).
</verification>

<success_criteria>
- All markdown files are under docs/src/ (confirmed by git status renames)
- gen_ref_pages.py is at docs/scripts/gen_ref_pages.py
- mkdocs.yml contains `docs_dir: docs/src`, updated script path, and updated edit_uri
- `uv run --group docs mkdocs build --strict` passes with exit code 0
</success_criteria>

<output>
After completion, create `.planning/quick/6-restructure-docs-layout-move-docs-conten/6-SUMMARY.md`
</output>
