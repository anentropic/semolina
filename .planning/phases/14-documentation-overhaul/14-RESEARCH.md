# Phase 14: Documentation Overhaul - Research

**Researched:** 2026-02-22
**Domain:** MkDocs Material configuration, Diataxis documentation framework, technical writing quality
**Confidence:** HIGH

## Summary

This phase restructures the Cubano documentation site around the Diataxis framework, reorganizes navigation using MkDocs Material's top-tabs feature, rewrites all prose content, and establishes CLAUDE.md quality gates. The project has 11 user-facing documentation files plus auto-generated API reference. The existing MkDocs Material installation (>=9.7.0) already supports all required features -- `navigation.tabs`, `pymdownx.tabbed` with `alternate_style`, and content code tabs are all available with no new dependencies needed.

Two Claude Code agent skills are critical to the workflow: `diataxis-documentation` (at `~/.claude/skills/diataxis-documentation/`) for content classification and structure guidance, and `humanizer` (at `~/.claude/skills/humanizer/`) for tone review. Both skills have detailed reference files and must be actively invoked during content writing -- not used as vague guidance.

**Primary recommendation:** Split into three plans: (1) mkdocs.yml navigation restructure with tabs enabled and file reorganization, (2) content rewrite using diataxis skill for each page, (3) humanizer tone pass on all content plus CLAUDE.md quality gate additions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Enable MkDocs Material top-tabs navigation
- Reorganize tabs around Diataxis categories: **Home | Tutorials | How-To Guides | Reference | Explanation**
- Changelog moves out of main nav -- footer link only
- Each tab maps directly to a Diataxis category
- Claude classifies existing guides into Diataxis categories using the `diataxis-documentation` skill (not guesswork)
- Existing code examples are preserved; all prose is rewritten from scratch guided by Diataxis analysis of structure, target audience, and tone
- Reference tab: auto-generated API docs from mkdocstrings, plus any hand-written reference pages Claude determines add value
- Explanation tab: start small with 1-2 foundational pages, grow over time
- Lead with "What is a Semantic View?" -- brief elevator pitch, not exhaustive explanation
- Assume users already have semantic views defined in their warehouse
- Focus on where Cubano fits into the picture and target use cases
- Link out to warehouse vendors' docs for semantic view setup
- **Audience:** Data/analytics engineers who already work with semantic views and are comfortable with SQL and Python
- **Tone:** Warm but efficient (like FastAPI/Stripe docs) -- friendly without being wordy, just enough context
- **Perspective:** Second person ("you") -- direct and personal
- **Framing:** User already has the semantic view; docs explain how Cubano mirrors/shadows it
- All prose must pass through the `humanizer` skill for tone review
- **Tutorials:** Runnable code -- works if pasted with right imports, show imports and output
- **How-to guides:** Illustrative snippets -- show the key concept, reader supplies setup
- **Reference:** Auto-generated with type signatures
- **SQL output:** Show generated SQL in how-to guides only (not tutorials)
- **SQL dialects:** Use MkDocs tabbed content to show Snowflake and Databricks SQL side by side
- **Cross-referencing:** Each guide is self-contained with "See also" links -- reader can jump in anywhere
- Add formal documentation quality gate: any phase that changes public API surface must update corresponding docs
- CLAUDE.md must mandate use of `diataxis-documentation` and `humanizer` skills when writing or modifying docs -- not optional
- CLAUDE.md must include example standards: tutorials runnable, how-to illustrative with tabbed SQL, self-contained pages with "See also" links

### Claude's Discretion
- Tutorial structure: single guided journey vs separate tutorials -- pick based on content volume and Diataxis best practices
- Whether to add hand-written reference pages beyond auto-generated docs (e.g. field types table, cheat sheet)
- Which additional explanation pages (if any) beyond "What is a Semantic View?"
- Humanizer enforcement level: all modified pages vs new content only -- determine when it adds value vs overhead

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCS-01 | Getting started guide with install, model definition, first query example | Existing installation.md + first-query.md become Tutorial content; rewrite prose per diataxis tutorial rules, preserve code examples |
| DOCS-02 | API reference auto-generated from docstrings (MkDocs + mkdocstrings) | Already working via gen_ref_pages.py + mkdocstrings; moves under Reference tab in new nav |
| DOCS-03 | Query language guide: .metrics(), .dimensions(), .filter(), .order_by(), .limit() | Existing queries.md + ordering.md become How-To Guides; rewrite prose per diataxis how-to rules |
| DOCS-04 | Query language guide: Q-objects and AND/OR composition | Already satisfied (Phase 13-02); filtering.md content becomes How-To Guide |
| DOCS-05 | Backend comparison: Snowflake vs Databricks differences and migration tips | Existing backends/overview.md becomes How-To Guide with tabbed SQL examples (Snowflake/Databricks side by side) |
| DOCS-06 | MkDocs + Material theme configured locally | Already satisfied; this phase adds navigation.tabs feature flag |
| DOCS-07 | Explore and integrate useful mkdocs plugins | Already configured (search, gen-files, literate-nav, section-index, mkdocstrings); no new plugins needed for tab nav |
| DOCS-08 | GitHub Actions workflow builds docs on push to main | Already satisfied; no changes needed for nav restructure |
| DOCS-09 | Built docs auto-deploy to GitHub Pages | Already satisfied; no changes needed |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mkdocs-material | >=9.7.0 | Documentation theme with tabs, tabbed content, code annotations | Already installed; `navigation.tabs` feature available since v6.x |
| mkdocstrings[python] | >=0.26.0 | Auto-generated API reference from docstrings | Already installed; drives Reference tab |
| pymdownx.tabbed | built-in | Content tabs for side-by-side SQL dialect examples | Already configured with `alternate_style: true` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mkdocs-gen-files | >=0.5.0 | Generate reference pages dynamically | Already installed; gen_ref_pages.py |
| mkdocs-literate-nav | >=0.6.0 | Markdown-based nav for reference section | Already installed; SUMMARY.md pattern |
| mkdocs-section-index | >=0.3.0 | Section index pages | Already installed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| navigation.tabs | navigation.sections only | Tabs provide clear Diataxis category separation at top level; sections alone bury categories in sidebar |
| navigation.tabs.sticky | navigation.tabs (non-sticky) | Sticky keeps tabs visible on scroll; may feel cluttered on small docs sites. Recommend adding for better UX. |

**Installation:** No new dependencies needed. All required packages are already in the `docs` dependency group.

## Architecture Patterns

### Recommended Docs Structure (After Reorganization)
```
docs/src/
├── index.md                          # Home tab landing page
├── tutorials/
│   ├── index.md                      # Tutorials tab landing (optional section index)
│   ├── installation.md               # From guides/installation.md (rewritten)
│   └── first-query.md                # From guides/first-query.md (rewritten)
├── how-to/
│   ├── index.md                      # How-To Guides tab landing (optional section index)
│   ├── models.md                     # From guides/models.md
│   ├── queries.md                    # From guides/queries.md
│   ├── filtering.md                  # From guides/filtering.md
│   ├── ordering.md                   # From guides/ordering.md
│   ├── backends/
│   │   ├── overview.md               # From guides/backends/overview.md
│   │   ├── snowflake.md              # From guides/backends/snowflake.md
│   │   └── databricks.md             # From guides/backends/databricks.md
│   ├── codegen.md                    # From guides/codegen.md
│   └── warehouse-testing.md          # From guides/warehouse-testing.md
├── reference/                        # Auto-generated (unchanged)
│   └── SUMMARY.md
├── explanation/
│   ├── index.md                      # Explanation tab landing (optional section index)
│   └── semantic-views.md             # NEW: "What is a Semantic View?"
└── changelog.md                      # Moved to footer link only
```

### Pattern 1: MkDocs Material Top Tabs Navigation
**What:** Each Diataxis category becomes a top-level nav section rendered as a tab
**When to use:** When documentation has distinct content categories that should be immediately discoverable
**Configuration:**
```yaml
# mkdocs.yml
theme:
  features:
    - navigation.tabs
    - navigation.tabs.sticky    # recommended for usability

nav:
  - Home:
      - index.md
  - Tutorials:
      - tutorials/index.md
      - tutorials/installation.md
      - tutorials/first-query.md
  - How-To Guides:
      - how-to/index.md
      - how-to/models.md
      - how-to/queries.md
      - how-to/filtering.md
      - how-to/ordering.md
      - Backends:
          - how-to/backends/overview.md
          - how-to/backends/snowflake.md
          - how-to/backends/databricks.md
      - how-to/codegen.md
      - how-to/warehouse-testing.md
  - Reference: reference/
  - Explanation:
      - explanation/index.md
      - explanation/semantic-views.md
```
Source: Context7 /websites/squidfunk_github_io_mkdocs-material -- navigation.tabs configuration

### Pattern 2: Changelog as Footer Link
**What:** Remove changelog from main nav, add as footer link
**Configuration:**
```yaml
# mkdocs.yml
extra:
  social:
    - icon: material/text-box-outline
      link: /changelog/
      name: Changelog

# Or use theme customization:
theme:
  custom_dir: overrides
```
Alternatively, use the `extra` footer configuration or a simple `nav` exclusion. The simplest approach: keep changelog.md in docs/src but don't list it in `nav`. It remains accessible via direct URL but not in navigation.

### Pattern 3: Tabbed SQL Dialect Examples
**What:** Show Snowflake and Databricks SQL side-by-side in how-to guides
**When to use:** How-to guides only (per user decision: not in tutorials)
**Example:**
```markdown
=== "Snowflake"

    ```sql
    SELECT AGG("revenue"), "country"
    FROM "sales"
    GROUP BY ALL
    ```

=== "Databricks"

    ```sql
    SELECT MEASURE(`revenue`), `country`
    FROM `sales`
    GROUP BY ALL
    ```
```
Source: Context7 -- pymdownx.tabbed extension with alternate_style

### Pattern 4: Diataxis Content Classification Workflow
**What:** Classify each existing page, then rewrite prose according to its Diataxis type
**Workflow:**
1. Load diataxis-documentation skill SKILL.md
2. For each existing page, ask two questions: (a) Action or Cognition? (b) Study or Work?
3. Map to category: Action+Study=Tutorial, Action+Work=How-To, Cognition+Work=Reference, Cognition+Study=Explanation
4. Load the appropriate reference file (tutorials.md, how-to-guides.md, reference.md, explanation.md)
5. Rewrite prose following the rules for that category
6. Preserve all existing code examples verbatim

### Pattern 5: Self-Contained Pages with See Also
**What:** Each page works standalone; cross-references via "See also" section at bottom
**Example:**
```markdown
## See also

- [Defining models](../how-to/models.md) -- how to define SemanticView subclasses
- [Filtering](../how-to/filtering.md) -- field operators and boolean composition
- [API Reference: fields](../reference/cubano/fields.md) -- full Field class documentation
```

### Anti-Patterns to Avoid
- **Mixing Diataxis types in one page:** A tutorial that stops to explain theory, or a how-to guide that teaches basics. Split content across types and link.
- **Empty structure scaffolding:** Don't create placeholder pages with no content. Only create pages that have real content.
- **Duplicating API reference in prose:** How-to guides should link to reference, not re-list all method signatures.
- **Over-explaining in tutorials:** Tutorials teach by doing. "Add this line" not "Understanding why this line works is crucial because..."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Content classification | Manual guesswork about page types | `diataxis-documentation` skill | Skill has formal decision tree and reference files for each type |
| Tone review | Ad-hoc style editing | `humanizer` skill | Systematic detection of 24 AI writing patterns |
| API reference pages | Hand-written API docs | mkdocstrings auto-generation | Already working; stays in sync with code automatically |
| Tab navigation | Custom HTML templates | `navigation.tabs` feature flag | Single YAML line; Material handles rendering |
| Content tabs | Custom JavaScript | `pymdownx.tabbed` extension | Already configured; handles tab state and accessibility |

**Key insight:** The two agent skills (diataxis-documentation and humanizer) are the primary tools for this phase. The MkDocs configuration changes are mechanical. The content work is where quality comes from.

## Common Pitfalls

### Pitfall 1: Breaking Existing Links During File Moves
**What goes wrong:** Moving files from `guides/` to `tutorials/` or `how-to/` breaks internal cross-references and any external links to the docs site.
**Why it happens:** MkDocs uses file paths as URLs. Renaming `guides/first-query.md` to `tutorials/first-query.md` changes the URL from `/guides/first-query/` to `/tutorials/first-query/`.
**How to avoid:** (a) Update ALL internal `[link](path.md)` references in every .md file after moving, (b) Consider using mkdocs-redirects plugin for external URL preservation, (c) Run `mkdocs build --strict` after every move -- it catches broken links.
**Warning signs:** `mkdocs build` warnings about missing pages or broken links.

### Pitfall 2: Navigation Tabs Not Appearing
**What goes wrong:** Adding `navigation.tabs` feature but tabs don't render.
**Why it happens:** Tabs only appear when there are at least 2 top-level `nav` sections. Also, tabs only render for viewports above 1220px -- on mobile they remain as sidebar sections.
**How to avoid:** Ensure `nav:` in mkdocs.yml has multiple top-level entries. Test at desktop resolution.
**Warning signs:** Tabs visible on desktop but missing on narrow browser window (expected behavior, not a bug).

### Pitfall 3: Rewriting Code Examples During Prose Rewrite
**What goes wrong:** Prose rewrite accidentally modifies working code examples, breaking doctest validation or introducing incorrect API usage.
**Why it happens:** When rewriting a page from scratch, it's tempting to "improve" code too.
**How to avoid:** User decision is explicit: preserve existing code examples, rewrite prose only. Copy code blocks verbatim from existing pages into rewritten pages.
**Warning signs:** `uv run pytest --doctest-modules` failures, incorrect import paths in examples.

### Pitfall 4: Humanizer Skill Over-Correcting Technical Prose
**What goes wrong:** Humanizer removes patterns that are actually appropriate for technical documentation (e.g., "Additionally" in a list of features, structured bullet points).
**Why it happens:** Humanizer is tuned for general prose, not specifically for technical documentation. Some patterns it flags (bold headers in lists, structured sequences) are legitimate in docs.
**How to avoid:** Apply humanizer as a review pass, not a blind rewrite. Technical documentation conventions (structured lists, precise terminology, step-by-step formatting) should be preserved. The "warm but efficient" tone target (like FastAPI/Stripe) still uses structured formatting.
**Warning signs:** Docs that read well but lose scannability and structure.

### Pitfall 5: Explanation Pages That Teach or Instruct
**What goes wrong:** "What is a Semantic View?" page starts giving step-by-step instructions or becomes a tutorial.
**Why it happens:** It feels incomplete to explain something without showing how to use it.
**How to avoid:** Explanation pages explain concepts and link to tutorials/how-tos for action. "What is a Semantic View?" should explain the concept, where Cubano fits, and link out -- not walk through defining a model.
**Warning signs:** Page has code examples with "do this next" language.

### Pitfall 6: CLAUDE.md Quality Gates That Are Too Restrictive
**What goes wrong:** CLAUDE.md mandates full humanizer + diataxis pass on every single doc change, creating friction for small fixes.
**Why it happens:** Overly rigid rules that don't scale to small changes (typo fixes, version bumps).
**How to avoid:** Tier the quality gates: (a) All new pages: full diataxis + humanizer pass required, (b) Major rewrites: full pass required, (c) Minor fixes (typos, version numbers): not required, (d) API surface changes: corresponding doc update required (but not full rewrite).
**Warning signs:** Contributors skipping the quality gate entirely because it's too burdensome.

## Code Examples

### MkDocs Configuration: Enabling Tabs
```yaml
# Source: Context7 /websites/squidfunk_github_io_mkdocs-material
theme:
  name: material
  features:
    - navigation.tabs
    - navigation.tabs.sticky
    - navigation.instant
    - navigation.sections
    - navigation.top
    - navigation.tracking
    - toc.follow
    - content.code.copy
    - content.code.annotate
    - search.suggest
    - search.highlight
```

### MkDocs Configuration: Footer-Only Changelog
```yaml
# Keep changelog accessible via URL but not in main nav
# Option A: Simply omit from nav (page still builds, accessible via /changelog/)
nav:
  - Home:
      - index.md
  - Tutorials:
      - tutorials/installation.md
      - tutorials/first-query.md
  # ... other tabs ...
  # Note: changelog.md NOT listed here

# Option B: Add explicit footer link
extra:
  generator: false  # optional: hide "Made with MkDocs"
```

### Diataxis Classification of Existing Pages

Based on analysis of current content against Diataxis decision tree:

| Current Page | Current Type | Diataxis Classification | Destination |
|---|---|---|---|
| `index.md` | Landing page | Home (stays) | `index.md` |
| `guides/installation.md` | Getting started | Tutorial (learning, action) | `tutorials/installation.md` |
| `guides/first-query.md` | Getting started | Tutorial (learning, action) | `tutorials/first-query.md` |
| `guides/models.md` | Concept + how-to mix | How-To Guide (working, action) | `how-to/models.md` |
| `guides/queries.md` | How-to guide | How-To Guide (working, action) | `how-to/queries.md` |
| `guides/filtering.md` | How-to guide | How-To Guide (working, action) | `how-to/filtering.md` |
| `guides/ordering.md` | How-to guide | How-To Guide (working, action) | `how-to/ordering.md` |
| `guides/backends/overview.md` | Comparison + how-to | How-To Guide (working, action) | `how-to/backends/overview.md` |
| `guides/backends/snowflake.md` | Backend setup | How-To Guide (working, action) | `how-to/backends/snowflake.md` |
| `guides/backends/databricks.md` | Backend setup | How-To Guide (working, action) | `how-to/backends/databricks.md` |
| `guides/codegen.md` | Tool usage | How-To Guide (working, action) | `how-to/codegen.md` |
| `guides/warehouse-testing.md` | Tool usage | How-To Guide (working, action) | `how-to/warehouse-testing.md` |
| `reference/` | API docs | Reference (working, cognition) | `reference/` (unchanged) |
| `changelog.md` | Release notes | N/A (footer link) | footer link |
| NEW | Explanation | Explanation (studying, cognition) | `explanation/semantic-views.md` |

### Tutorial Structure Recommendation

Based on Diataxis tutorial guidelines and the current content volume, recommend a **single guided journey** tutorial that combines installation and first query into one flow, rather than splitting into two separate tutorials. Rationale:

- Cubano's getting-started path is short (install, define model, register engine, query, read results)
- Two separate tutorials for a 5-minute total flow creates unnecessary page transitions
- Diataxis tutorials emphasize "immediate success" -- one combined tutorial gets there faster

However, keep them as two pages if the single-page length exceeds comfortable reading (roughly 200 lines). The installation page is fairly short (88 lines) and first-query is moderate (144 lines). Combined they would be roughly 200 lines -- right at the boundary. **Recommendation: keep as two tutorial pages** for clean separation of concerns (setup vs. usage), but ensure the first page ends with a clear pointer to the second.

### Hand-Written Reference Pages Recommendation

The auto-generated API reference via mkdocstrings is comprehensive. Consider adding one hand-written reference page:

- **Field Types Quick Reference:** A concise table of Metric/Dimension/Fact with their accepted methods, operator overloads, and which query methods accept them. This is faster to scan than navigating the full auto-generated docs. Similar to Django's "Field types" reference page.

This is discretionary per CONTEXT.md. Only create if the content rewrite reveals a gap that auto-generated docs don't fill well.

### Explanation Content: "What is a Semantic View?"

Per user decisions:
- Brief elevator pitch, not exhaustive
- Assume users already have semantic views in their warehouse
- Focus on where Cubano fits
- Link out to vendor docs for setup

Outline:
1. One-paragraph definition of semantic views (the concept)
2. How Snowflake (CREATE SEMANTIC VIEW) and Databricks (Metric Views) implement them
3. Where Cubano fits: a Python ORM that mirrors your existing warehouse views as typed models
4. Link to Snowflake docs for semantic view creation
5. Link to Databricks docs for metric view creation
6. "See also" links to tutorials and how-to guides

Additional explanation page to consider: "How Cubano generates SQL" -- explaining the dialect system, AGG() vs MEASURE(), identifier quoting. This content currently lives scattered across backend guides. Consolidating the "why" into an explanation page while the backend guides focus on "how to connect" would be a clean Diataxis separation. **Recommendation: add this as a second explanation page if time permits, but the semantic views page is the priority.**

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tabs` feature flag | `navigation.tabs` feature flag | MkDocs Material 6.x (2021) | Use prefixed name |
| Single sidebar navigation | Top tabs + sidebar | Available since Material 6.x | Clearer content organization |
| Single tab style | `alternate_style: true` for tabbed content | MkDocs Material 7.3.1 | Better mobile behavior; only supported style |

**Deprecated/outdated:**
- `tabs` feature flag (use `navigation.tabs` instead -- Material 6.x+)
- Non-alternate tab style for content tabs (use `alternate_style: true`)

## Open Questions

1. **mkdocs-redirects plugin for URL preservation**
   - What we know: Moving files from `guides/` to `tutorials/` and `how-to/` changes URLs. External links will break.
   - What's unclear: Whether anyone has linked to the current docs externally. The site is new and the project is pre-1.0.
   - Recommendation: Skip redirects for now. The site is new enough that URL breakage is low risk. If needed later, `mkdocs-redirects` is a simple addition.

2. **Section index pages for each tab**
   - What we know: Each Diataxis tab could have a landing page (e.g., `tutorials/index.md` with an overview of available tutorials).
   - What's unclear: Whether the `section-index` plugin handles this cleanly with tabs, or if it creates navigation duplication.
   - Recommendation: Create minimal index pages for Tutorials and How-To Guides tabs. The Explanation tab has few enough pages that a section index is unnecessary. Reference already uses the SUMMARY.md + literate-nav pattern.

3. **Tutorial runnability with MockEngine**
   - What we know: User decided tutorials must have runnable code. The existing first-query.md already uses MockEngine for this.
   - What's unclear: Whether MockEngine examples should include explicit output (e.g., showing what `print(row.country, row.revenue)` outputs).
   - Recommendation: Yes, show expected output. Diataxis tutorial guidelines emphasize "you should see: [result]" after each step. This is already partially done in existing content.

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/squidfunk_github_io_mkdocs-material` -- navigation.tabs configuration, pymdownx.tabbed extension, sticky tabs, content tabs syntax
- Diataxis-documentation skill SKILL.md + references/tutorials.md + references/how-to-guides.md -- framework definition, content type decision tree, writing rules
- Humanizer skill SKILL.md -- 24 AI writing pattern detection rules, before/after examples

### Secondary (MEDIUM confidence)
- Existing Cubano docs (11 pages reviewed in full) -- content inventory, current structure, code examples to preserve
- MkDocs Material official documentation (via Context7) -- feature flag names, configuration syntax

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies already installed, features verified in Context7
- Architecture: HIGH -- nav structure directly maps CONTEXT.md decisions to MkDocs Material features
- Pitfalls: HIGH -- based on direct analysis of current docs structure and known MkDocs Material behavior
- Content classification: HIGH -- each page analyzed against Diataxis decision tree with skill reference
- Skill integration: HIGH -- both skills read in full, workflow documented

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (stable domain; MkDocs Material and Diataxis are mature)
