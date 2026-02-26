# Phase 18: Fix invalid CREATE VIEW examples in first-query tutorial - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the Snowflake and Databricks DDL examples (lines 35-56 in `docs/src/tutorials/first-query.md`) to use valid syntax matching official warehouse documentation. The current `CREATE SEMANTIC VIEW` and `CREATE METRIC VIEW` examples use invented/incorrect syntax.

</domain>

<decisions>
## Implementation Decisions

### Example fidelity
- Use valid DDL syntax from official Snowflake/Databricks docs, but keep illustrative (placeholder table names like `source_table` are fine)
- Match official syntax closely, even if the examples end up looking significantly different from current ones. Accuracy over familiarity.
- Show a realistic but focused subset of the DDL — include clauses a user would actually need, skip rarely-used options
- If the Databricks DDL naturally distinguishes facts from dimensions, include a fact column to hint at the concept (the Sales model above doesn't use Fact, but a brief appearance is fine)

### Claude's Discretion
- Whether to include inline SQL comments mapping warehouse concepts to Cubano concepts, based on readability
- Source table design (column names, types) — should feel natural for a sales domain
- Any adjustments to the surrounding prose ("this model maps to a view like:") based on what the corrected DDL looks like

</decisions>

<specifics>
## Specific Ideas

- Reference the official docs: https://docs.snowflake.com/en/sql-reference/sql/create-view and https://docs.databricks.com/en/sql/language-manual/sql-ref-syntax-ddl-create-view.html
- The corrected examples should be recognizable to someone who has actually created semantic/metric views in their warehouse

</specifics>

<deferred>
## Deferred Ideas

- Better documentation for Cubano's `Fact` field type — Databricks metric views explicitly define "facts" which behave functionally like dimensions (informative distinction). Snowflake users need explanation that they can label some dimensions as facts. Deserves its own how-to or section in models docs.

</deferred>

---

*Phase: 18-fix-invalid-create-view-examples-in-first-query-tutorial*
*Context gathered: 2026-02-23*
