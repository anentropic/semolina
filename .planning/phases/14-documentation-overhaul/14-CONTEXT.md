# Phase 14: Documentation Overhaul - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Restructure docs navigation with MkDocs Material top-tabs, rewrite all doc content following the Diataxis framework, and improve prose tone to read as natural human-written technical writing. Code examples from existing docs are preserved; prose is rewritten from scratch. Establish CLAUDE.md guidance so future documentation follows the same standards.

</domain>

<decisions>
## Implementation Decisions

### Navigation structure
- Enable MkDocs Material top-tabs navigation
- Reorganize tabs around Diataxis categories: **Home | Tutorials | How-To Guides | Reference | Explanation**
- Changelog moves out of main nav — footer link only
- Each tab maps directly to a Diataxis category

### Diataxis content mapping
- Claude classifies existing guides into Diataxis categories using the `diataxis-documentation` skill (not guesswork)
- Existing code examples are preserved; all prose is rewritten from scratch guided by Diataxis analysis of structure, target audience, and tone
- Reference tab: auto-generated API docs from mkdocstrings, plus any hand-written reference pages Claude determines add value
- Explanation tab: start small with 1-2 foundational pages, grow over time

### Explanation content
- Lead with "What is a Semantic View?" — brief elevator pitch, not exhaustive explanation
- Assume users already have semantic views defined in their warehouse
- Focus on where Cubano fits into the picture and target use cases
- Link out to warehouse vendors' docs for semantic view setup
- Claude determines if additional explanation pages are warranted

### Writing voice & audience
- **Audience:** Data/analytics engineers who already work with semantic views and are comfortable with SQL and Python
- **Tone:** Warm but efficient (like FastAPI/Stripe docs) — friendly without being wordy, just enough context
- **Perspective:** Second person ("you") — direct and personal
- **Framing:** User already has the semantic view; docs explain how Cubano mirrors/shadows it
- All prose must pass through the `humanizer` skill for tone review

### Content depth & examples
- **Tutorials:** Runnable code — works if pasted with right imports, show imports and output
- **How-to guides:** Illustrative snippets — show the key concept, reader supplies setup
- **Reference:** Auto-generated with type signatures
- **SQL output:** Show generated SQL in how-to guides only (not tutorials)
- **SQL dialects:** Use MkDocs tabbed content to show Snowflake and Databricks SQL side by side
- **Cross-referencing:** Each guide is self-contained with "See also" links — reader can jump in anywhere

### Documentation quality gates (CLAUDE.md)
- Add formal documentation quality gate: any phase that changes public API surface must update corresponding docs
- CLAUDE.md must mandate use of `diataxis-documentation` and `humanizer` skills when writing or modifying docs — not optional
- CLAUDE.md must include example standards: tutorials runnable, how-to illustrative with tabbed SQL, self-contained pages with "See also" links

### Claude's Discretion
- Tutorial structure: single guided journey vs separate tutorials — pick based on content volume and Diataxis best practices
- Whether to add hand-written reference pages beyond auto-generated docs (e.g. field types table, cheat sheet)
- Which additional explanation pages (if any) beyond "What is a Semantic View?"
- Humanizer enforcement level: all modified pages vs new content only — determine when it adds value vs overhead

</decisions>

<specifics>
## Specific Ideas

- "Warm but efficient" tone demonstrated in discussion — like FastAPI/Stripe docs (see examples in CONTEXT conversation)
- Perspective correction: don't explain what a semantic view is from scratch — users already have them, explain how Cubano shadows their existing views
- Must actively use `diataxis-documentation` Agent Skill for content structure/classification and `humanizer` Agent Skill for tone review — not just as vague guidance but as active tools in the workflow
- Tabbed SQL output (Snowflake | Databricks) using MkDocs Material's built-in tab support

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-documentation-overhaul*
*Context gathered: 2026-02-22*
