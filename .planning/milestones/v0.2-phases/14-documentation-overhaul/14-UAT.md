---
status: resolved
phase: 14-documentation-overhaul
source: 14-01-SUMMARY.md, 14-02-SUMMARY.md, 14-03-SUMMARY.md
started: 2026-02-22T12:30:00Z
updated: 2026-02-22T18:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Docs site builds and serves
expected: `uv run mkdocs build --strict` passes with zero warnings. `uv run mkdocs serve` launches the site at localhost:8000.
result: issue
reported: "reference/ link on home page card is broken (no index.html at that path). Changelog footer link was agreed upon but never implemented."
severity: major

### 2. Top-tabs navigation structure
expected: Site has 5 sticky top-tabs: Home | Tutorials | How-To Guides | Reference | Explanation. Tabs persist while scrolling.
result: pass

### 3. Home page content and links
expected: Home page has a tagline framing Cubano for engineers with existing semantic views. Card links point to tutorials/ and how-to/ paths, all resolve correctly.
result: issue
reported: "Target user persona not elaborated enough, docs read like GSD planning sessions not end-user docs. API Reference card has LLM fluff ('Auto-generated from docstrings -- always current.' with sneaky em dash). MockEngine promoted to users (irrelevant). 'one API that works the same on Snowflake and Databricks' is awkward wording. Proposed byline: 'Cubano: the ORM for your Semantic Layer'."
severity: major

### 4. Tutorial: Installation page structure
expected: Step-by-step tutorial with numbered steps, `uv add cubano` with backend extras, and a verification step. Reads as a guided walkthrough, not a reference page.
result: issue
reported: "'Use a virtual environment' section should be part of the pip tab only, not shown for uv installs. 'Cubano has zero runtime dependencies by default' claim is inaccurate and keeps resurfacing."
severity: major

### 5. Tutorial: First Query page structure
expected: Step-by-step tutorial that walks through defining a model, creating an engine, building a query, and getting results. Each step has expected output shown. Code is runnable.
result: issue
reported: "'Define a model' needs more substantive detail and SQL example showing how model shadows warehouse view. 'Register an engine' uses MockEngine with fixture data as if writing a unit test -- completely wrong audience. Need to diagnose how requirements were so misunderstood and fix problems in the GSD plan docs. 'Build and run a query' is ok but reduce line length in blacken-docs to 60 chars for docs only."
severity: major

### 6. Explanation: Semantic Views page
expected: Concept-focused page explaining what semantic views are. Links to Snowflake and Databricks vendor docs for setup details. No step-by-step instructions -- purely explanatory.
result: issue
reported: "Good overall, but add direct links to each warehouse's specific view docs (Snowflake Semantic Views, Databricks Metric Views)."
severity: minor

### 7. How-to guide structure and headings
expected: How-to guides use action-verb titles. Content is goal-oriented for competent users. Each page has a "See also" section at the bottom.
result: issue
reported: "Setting up a warehouse connection should come first in guide ordering. Also need API design work for semantic views in different Snowflake schemas."
severity: major

### 8. Tabbed SQL dialect examples
expected: Guides that show SQL output have tabbed Snowflake/Databricks examples. Tabs appear inline after the Python code that generates the SQL.
result: issue
reported: "Show tabbed SQL examples sooner -- don't wait until introducing .to_sql() method. First example in each subhead should have them so user understands how the interface translates."
severity: major

### 9. Backend comparison page
expected: backends/overview.md has side-by-side tabbed SQL comparison blocks covering dialect differences between Snowflake and Databricks.
result: issue
reported: "Reword 'Cubano supports two data warehouse backends' to bullet list format (natural to extend). Remove 'Compare backends' section -- comparing SQL syntax is pointless fluff. Keep MockEngine example here but remove cross-ref to first-query MockEngine example. Overall page should be practical (which backend, how to connect) not a SQL syntax showcase."
severity: major

### 10. Writing tone and voice
expected: All pages use second person ("you"), warm-but-efficient tone (like FastAPI/Stripe docs). No AI vocabulary, no promotional language.
result: pass

## Summary

total: 10
passed: 2
issues: 8
pending: 0
skipped: 0

## Gaps

- truth: "Home page reference/ card link resolves correctly and changelog has footer link"
  status: resolved
  reason: "User reported: reference/ link broken (no index.html), changelog footer link never implemented"
  severity: major
  test: 1
  root_cause: "gen_ref_pages.py never writes reference/index.md; SUMMARY.md has no top-level index entry for section-index to promote. Changelog removed from nav but no footer mechanism (extra.social, custom_dir override) was created."
  artifacts:
    - path: "docs/src/index.md"
      issue: "Line 34: reference/ link resolves to path with no backing file"
    - path: "mkdocs.yml"
      issue: "No extra: section, no custom_dir for footer template, no changelog nav entry"
    - path: "docs/scripts/gen_ref_pages.py"
      issue: "Never writes reference/index.md"
  missing:
    - "Create reference/index.md (hand-written or generated) so reference/ URL resolves"
    - "Add footer link for changelog via MkDocs Material extra config or template override"
  debug_session: ""

- truth: "Home page content uses correct persona, tone, and byline for end users"
  status: resolved
  reason: "User reported: LLM fluff text, MockEngine promoted to users, awkward wording, missing persona elaboration. Proposed byline: 'Cubano: the ORM for your Semantic Layer'"
  severity: major
  test: 3
  root_cause: "Plan said 'Keep the Quick Example code block unchanged' (which used MockEngine), perpetuating wrong narrative. CONTEXT defined tone but never specified positioning statement or byline. Plan said 'Consider adding a brief tagline' -- discretionary wording produced generic copy."
  artifacts:
    - path: "docs/src/index.md"
      issue: "Card descriptions have LLM fluff, MockEngine in quick example, no persona-specific byline"
    - path: ".planning/phases/14-documentation-overhaul/14-02-PLAN.md"
      issue: "Task 2: 'Keep Quick Example unchanged' and 'Consider adding tagline' (discretionary)"
    - path: ".planning/phases/14-documentation-overhaul/14-CONTEXT.md"
      issue: "Defines audience but not home page copy requirements or positioning"
  missing:
    - "Explicit byline requirement: 'Cubano: the ORM for your Semantic Layer'"
    - "Quick example should show real warehouse usage, not MockEngine"
    - "Card descriptions must be user-facing, not meta/internal"
  debug_session: ""

- truth: "Installation tutorial is audience-appropriate with conditional venv advice"
  status: resolved
  reason: "User reported: venv section should be pip-tab-only, 'zero runtime dependencies' claim is inaccurate"
  severity: major
  test: 4
  root_cause: "Plan said nothing about pip vs uv UX differences; agent placed venv tip as global admonition outside tab structure. 'Zero runtime dependencies' claim inherited from earlier content without verification; RESEARCH phase did not cover dependency accuracy."
  artifacts:
    - path: "docs/src/tutorials/installation.md"
      issue: "Lines 22-31: venv tip visible to all users; line 34: false zero-deps claim"
    - path: ".planning/phases/14-documentation-overhaul/14-02-PLAN.md"
      issue: "Task 1 silent on conditional advice per package manager"
  missing:
    - "Move venv advice inside pip tab only"
    - "Remove zero runtime dependencies claim"
    - "Add dependency accuracy audit to planning requirements"
  debug_session: ".planning/debug/uat-gaps-3-4-5-doc-content.md"

- truth: "First query tutorial uses real warehouse examples, not MockEngine test fixtures"
  status: resolved
  reason: "User reported: model step needs SQL example of warehouse view, engine step uses MockEngine inappropriately, need to diagnose how GSD plan docs led to this misunderstanding. Reduce docs code line length to 60 chars."
  severity: major
  test: 5
  root_cause: "Requirement contradiction never resolved: CONTEXT said 'user already has semantic view' (implies real warehouse) but also 'runnable code' (implies self-contained). RESEARCH resolved this without user input by choosing MockEngine. Plan inherited it as a requirement. Execution followed plan correctly -- the failure was upstream in research/planning."
  artifacts:
    - path: "docs/src/tutorials/first-query.md"
      issue: "Tutorial teaches MockEngine fixture loading (unit test pattern) instead of real warehouse workflow"
    - path: ".planning/phases/14-documentation-overhaul/14-RESEARCH.md"
      issue: "Open question #3 resolved MockEngine as 'settled fact' without user input"
    - path: ".planning/phases/14-documentation-overhaul/14-02-PLAN.md"
      issue: "'Walk through: define a model, register a MockEngine' baked in as requirement"
    - path: ".planning/phases/14-documentation-overhaul/14-CONTEXT.md"
      issue: "Unresolved contradiction: 'user has semantic view' vs 'runnable code'"
  missing:
    - "Tutorial should show real warehouse connection with 'swap your connection string' pattern"
    - "Add SQL example showing how view='sales' maps to warehouse semantic view"
    - "Add blacken-docs line length 60 chars requirement to CLAUDE.md or pyproject.toml"
    - "CONTEXT needs audience workflow narrative section, not just tone"
  debug_session: ".planning/debug/uat-gaps-3-4-5-doc-content.md"

- truth: "Semantic views page links directly to each warehouse's view documentation"
  status: resolved
  reason: "User reported: add direct links to Snowflake Semantic Views and Databricks Metric Views docs"
  severity: minor
  test: 6
  root_cause: "Warehouse doc links exist inline in body text (lines 12, 17) but are absent from the See also section where readers scan for external references."
  artifacts:
    - path: "docs/src/explanation/semantic-views.md"
      issue: "Lines 43-49: See also section has only internal Cubano links, no vendor doc links"
  missing:
    - "Promote Snowflake and Databricks vendor doc links to See also section"
  debug_session: ""

- truth: "How-to guide ordering starts with warehouse connection setup"
  status: resolved
  reason: "User reported: connection setup should come first. Also need API design for views in different Snowflake schemas."
  severity: major
  test: 7
  root_cause: "Nav structured around Cubano concepts (models, queries, filtering) not user workflow sequence. Backends section placed after all query guides even though users cannot run examples without first connecting. models.md only shows bare view='sales' with no schema qualification."
  artifacts:
    - path: "mkdocs.yml"
      issue: "Lines 99-108: Backends section last in how-to nav"
    - path: "docs/src/how-to/index.md"
      issue: "Lines 13-17: section ordering matches nav"
    - path: "docs/src/how-to/models.md"
      issue: "Lines 8-22: view= only shows bare name, no schema qualification"
  missing:
    - "Move Backends section to top of how-to nav in mkdocs.yml and index.md"
    - "Document multi-schema view= names or note current limitation in models.md"
  debug_session: ""

- truth: "Tabbed SQL examples appear early in each guide section"
  status: resolved
  reason: "User reported: show tabbed SQL sooner, first example in each subhead should have them"
  severity: major
  test: 8
  root_cause: "Tabs added reactively at .to_sql() introduction point (queries.md line 138) and selectively in filtering.md, rather than systematically after every first Python example under each subheading."
  artifacts:
    - path: "docs/src/how-to/queries.md"
      issue: "Lines 22-127: seven subheadings with Python examples but no SQL tabs before line 138"
    - path: "docs/src/how-to/filtering.md"
      issue: "Named filter method subsections (lines 62-116) and AND/NOT/nested sections (lines 152-213) lack SQL tabs"
    - path: "docs/src/how-to/models.md"
      issue: "Dimension and Fact sections (lines 62-81) have no SQL output"
  missing:
    - "Add tabbed SQL block after first Python example in every how-to guide subheading"
  debug_session: ""

- truth: "Backend overview is practical (connection-focused) not a SQL syntax comparison"
  status: resolved
  reason: "User reported: use bullet list for backends, remove Compare backends section and SQL comparison fluff, keep MockEngine here only, remove cross-ref to first-query MockEngine"
  severity: major
  test: 9
  root_cause: "Page written as comparison reference (SQL dialect blocks) rather than practical connection guide. SQL differences already shown in context throughout how-to guides; repeating here is disconnected fluff."
  artifacts:
    - path: "docs/src/how-to/backends/overview.md"
      issue: "Lines 8-16: Compare backends table (remove); lines 18-84: SQL differences section (remove); line 148: cross-ref to first-query MockEngine (remove)"
    - path: "docs/src/how-to/index.md"
      issue: "Line 15: description says 'compare...see SQL differences' (update to match new purpose)"
  missing:
    - "Remove Compare backends table and SQL differences section"
    - "Add bullet list of available backends near top"
    - "Remove first-query cross-reference from MockEngine section"
    - "Update index.md description"
  debug_session: ""
