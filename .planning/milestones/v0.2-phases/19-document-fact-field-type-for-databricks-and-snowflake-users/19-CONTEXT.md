# Phase 19: Document Fact field type for Databricks and Snowflake users - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Improve the documentation of the `Fact` field type within the existing `models.md` how-to guide. This is a documentation-only phase: no new features, no codegen changes. Goal is to give Snowflake users and Databricks users clear guidance on what `Fact` means in their context and when to use it.

Codegen output documentation (how Fact fields appear in `cubano codegen` SQL/YAML) is explicitly out of scope — the codegen is being revisited in a separate phase.

</domain>

<decisions>
## Implementation Decisions

### Documentation placement
- Expand the existing `### Fact fields` section in `docs/src/how-to/models.md` in-place
- Do not create a new standalone page — the field type docs belong together
- Claude's discretion: whether to update the comparison table wording and whether `semantic-views.md` (explanation page) needs a mention of Fact

### Warehouse divergence
- Explain the Snowflake vs Databricks divergence prominently and explicitly within the Fact section
  - **Snowflake users:** The `Fact` type maps to the `FACTS` clause in your `CREATE SEMANTIC VIEW` — use Fact for columns declared there
  - **Databricks users:** Databricks metric views have no native fact concept — everything non-aggregate is a `dimension:`. Use `Fact` for raw numeric columns you want to semantically distinguish from categorical dimensions
- At query time in Cubano, `Fact` and `Dimension` behave identically (same SQL generated for both — `SELECT "col" FROM ... GROUP BY ALL`). The divergence is conceptual/semantic, not runtime

### When to use Fact vs Dimension
- The **default recommendation** is to use `Dimension` — `Fact` is an intentional opt-in
- Use `Fact` when either of these apply:
  1. **Semantic precision** (primary reason): the column is a raw event-level numeric (unit_price, quantity, amount) that you want to distinguish from categorical grouping attributes — signals intent to teammates and future code readers
  2. **Snowflake alignment**: your Snowflake semantic view definition uses a FACTS clause for this column — match that designation in Cubano
- Include inline prose examples of the distinction:
  - Fact: `unit_price`, `quantity`, `line_amount` (raw numerics from a fact/transaction table)
  - Dimension: `country`, `product_category`, `order_date` (categorical grouping attributes)

### Claude's Discretion
- Whether to update the comparison table `Use for` description for Fact
- Whether to touch `semantic-views.md` explanation page (only if it materially improves conceptual grounding without being redundant)
- Exact wording of the warehouse-specific callouts (keep warm but efficient, avoid over-explaining)

</decisions>

<specifics>
## Specific Ideas

- The Fact/Dimension distinction has roots in **star schema** design: fact tables hold raw event-level measurements, dimension tables hold descriptive context. Referencing this origin may help SQL-native analytics engineers recognize the concept — use sparingly and only if it clarifies rather than overcomplicates.
- "Default to Dimension, Fact is optional" framing should be explicit — the docs should say this directly so users don't spend time second-guessing

</specifics>

<deferred>
## Deferred Ideas

- Codegen output documentation for Fact fields (Snowflake `FACTS` clause, Databricks `dimensions:` mapping) — separate phase, codegen direction being revisited
- Star schema deep-dive explanation content — out of scope for how-to guide; could be added to explanation page in a future phase if needed

</deferred>

---

*Phase: 19-document-fact-field-type-for-databricks-and-snowflake-users*
*Context gathered: 2026-02-24*
