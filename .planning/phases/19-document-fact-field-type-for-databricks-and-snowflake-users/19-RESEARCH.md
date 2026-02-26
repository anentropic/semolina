# Phase 19: Document Fact Field Type for Databricks and Snowflake Users - Research

**Researched:** 2026-02-24
**Domain:** Technical documentation (how-to guide expansion) — no code changes
**Confidence:** HIGH

## Summary

Phase 19 is a pure documentation task. The scope is narrow and tightly bounded: expand the existing `### Fact fields` section in `docs/src/how-to/models.md` in-place. No new pages, no code changes, no codegen documentation.

The key editorial challenge is explaining a concept that diverges across warehouses. Snowflake has an explicit `FACTS` clause in `CREATE SEMANTIC VIEW` — facts are row-level numeric building blocks that help construct dimensions and metrics. Databricks metric views have no native fact concept whatsoever — everything non-aggregate is a `dimension:` in YAML. Cubano's `Fact` field type resolves this divergence by serving both audiences: Snowflake users get a direct mapping to their warehouse's `FACTS` clause, and Databricks users get a semantic signal to distinguish raw event-level numerics from categorical grouping attributes.

The second editorial challenge is setting expectations about runtime behavior. `Fact` and `Dimension` generate identical SQL (`SELECT "col" FROM ... GROUP BY ALL`). The distinction is conceptual and intent-signaling only, not a runtime difference. The doc must say this clearly, and it must also say "default to `Dimension` — `Fact` is an intentional opt-in."

**Primary recommendation:** Rewrite the `### Fact fields` section (~15 lines) and optionally update the comparison table's `Use for` cell. The explanation page (`semantic-views.md`) does not need updating — it already mentions Snowflake's `FACTS` is not one of its three main constructs, and adding Fact there would be redundant with the how-to guide.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Documentation placement:**
- Expand the existing `### Fact fields` section in `docs/src/how-to/models.md` in-place
- Do not create a new standalone page — the field type docs belong together

**Warehouse divergence:**
- Explain the Snowflake vs Databricks divergence prominently and explicitly within the Fact section
  - **Snowflake users:** The `Fact` type maps to the `FACTS` clause in your `CREATE SEMANTIC VIEW` — use `Fact` for columns declared there
  - **Databricks users:** Databricks metric views have no native fact concept — everything non-aggregate is a `dimension:`. Use `Fact` for raw numeric columns you want to semantically distinguish from categorical dimensions
- At query time in Cubano, `Fact` and `Dimension` behave identically (same SQL generated for both — `SELECT "col" FROM ... GROUP BY ALL`). The divergence is conceptual/semantic, not runtime

**When to use Fact vs Dimension:**
- The **default recommendation** is to use `Dimension` — `Fact` is an intentional opt-in
- Use `Fact` when either of these apply:
  1. **Semantic precision** (primary reason): the column is a raw event-level numeric (`unit_price`, `quantity`, `amount`) that you want to distinguish from categorical grouping attributes — signals intent to teammates and future code readers
  2. **Snowflake alignment**: your Snowflake semantic view definition uses a `FACTS` clause for this column — match that designation in Cubano
- Include inline prose examples of the distinction:
  - Fact: `unit_price`, `quantity`, `line_amount` (raw numerics from a fact/transaction table)
  - Dimension: `country`, `product_category`, `order_date` (categorical grouping attributes)

### Claude's Discretion

- Whether to update the comparison table `Use for` description for `Fact`
- Whether to touch `semantic-views.md` explanation page (only if it materially improves conceptual grounding without being redundant)
- Exact wording of the warehouse-specific callouts (keep warm but efficient, avoid over-explaining)

### Deferred Ideas (OUT OF SCOPE)

- Codegen output documentation for Fact fields (Snowflake `FACTS` clause, Databricks `dimensions:` mapping) — separate phase, codegen direction being revisited
- Star schema deep-dive explanation content — out of scope for how-to guide; could be added to explanation page in a future phase if needed
</user_constraints>

---

## Standard Stack

This phase has no software dependencies. The only tooling involved is the documentation build chain.

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| MkDocs Material | As in pyproject.toml | Renders `models.md` to HTML | Project standard |
| mkdocstrings | As in pyproject.toml | Auto-generates API reference | Project standard |
| `uv run mkdocs build --strict` | — | Quality gate for docs | Project standard |

### No Installation Required

No new dependencies. This phase edits one existing file (and optionally a second). The quality gate is:

```bash
uv run mkdocs build --strict
```

## Architecture Patterns

### Pattern 1: How-to Guide Section Anatomy (Project Standard)

**What:** The existing `### Fact fields` section follows the pattern used by `### Metric fields` and `### Dimension fields`: brief prose description → Python snippet → tabbed SQL output.

**Current `### Fact fields` content (lines 110–135 of `docs/src/how-to/models.md`):**

```markdown
### Fact fields

A `Fact` represents a raw numeric value in a fact table. Unlike a `Metric`, a Fact is not
pre-aggregated and can appear in `.dimensions()` for grouping or calculation purposes:

```python
class Orders(SemanticView, view="orders"):
    unit_price = Fact()  # raw price column, not aggregated
    quantity = Fact()
```

=== "Snowflake"

    ```sql
    SELECT "unit_price", "quantity"
    FROM "orders"
    GROUP BY ALL
    ```

=== "Databricks"

    ```sql
    SELECT `unit_price`, `quantity`
    FROM `orders`
    GROUP BY ALL
    ```
```

**What needs to change:** The prose description is thin. It explains what `Fact` is superficially but does not:
1. Tell users when to use it vs `Dimension`
2. Explain the Snowflake FACTS clause mapping
3. Explain that Databricks has no native fact concept
4. Set the "default to Dimension" expectation

### Pattern 2: MkDocs Admonition Callouts

The existing `models.md` uses admonitions for warehouse-specific tips (e.g., the "Views in non-default schemas" tip). Warehouse-divergence callouts could use `!!! note "Snowflake"` / `!!! note "Databricks"` blocks, or they can live inline as prose paragraphs with bold lead-ins.

**Recommendation:** Inline prose with bold warehouse names (e.g., **Snowflake users:**) is lighter than admonitions for conceptual notes that are part of a natural reading flow. Reserve admonitions for tips and warnings that readers might skip past. This matches the CONTEXT.md style of the warehouse-divergence text.

### Pattern 3: Comparison Table Update

**Current table row for Fact:**

| Field | Use for | Accepted by |
|-------|---------|-------------|
| `Fact` | Raw numeric values used in grouping or calculations | `.dimensions()` |

**Issue:** "Raw numeric values used in grouping or calculations" understates the semantic distinction and doesn't mention "when to use." Could become: "Raw event-level numeric columns (`unit_price`, `quantity`); signals intent vs a categorical `Dimension`"

This is Claude's discretion to update or leave. Given the new Fact section will explain this clearly, the table update is cosmetic but does make the reference scan faster.

### Anti-Patterns to Avoid

- **Putting codegen documentation here:** CONTEXT.md explicitly defers this. Do not mention how `Fact` appears in `cubano codegen` output.
- **Star schema tutorial:** Out of scope. A passing mention of star schema origin is permitted per CONTEXT.md "Specific Ideas" only if it clarifies; do not expand into a tutorial.
- **Adding a new page:** Locked decision — everything goes in `models.md` in-place.
- **Touching `semantic-views.md` without clear payoff:** The explanation page currently says "Each model is a Python class with `Metric` and `Dimension` fields." It does not mention `Fact`. Adding one sentence like "Fact fields provide a third classification for raw numerics — see [Defining models](../how-to/models.md)." would be minimal and useful. More than that would be redundant.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Warehouse-specific callouts | Custom MDX components, complex tabbed blocks | Inline prose with bold warehouse names | Simpler, matches existing style |
| SQL examples | New complex SQL | Reuse existing Snowflake/Databricks tabbed pattern | Fact SQL output is identical to Dimension SQL |

**Key insight:** The SQL examples for `Fact` fields are byte-for-byte identical to `Dimension` field SQL. The educational value in this section is all prose — the warehouse divergence explanation, when-to-use guidance, and examples of canonical Fact vs Dimension column names.

## Common Pitfalls

### Pitfall 1: Claiming Fact and Dimension Behave Differently at Runtime

**What goes wrong:** A doc author might imply or state that `Fact` generates different SQL than `Dimension` (e.g., "Fact columns aren't grouped the same way"). This is factually wrong and will confuse users who test it.

**Why it happens:** The conceptual distinction (fact vs dimension) suggests a runtime distinction in traditional OLAP. In Cubano's query engine, both field types go through `.dimensions()` and generate identical `GROUP BY ALL` SQL.

**How to avoid:** State explicitly: "At query time, `Fact` and `Dimension` produce identical SQL. The distinction is semantic — use `Fact` to signal intent."

**Warning signs:** Any sentence that starts "Unlike `Dimension`, `Fact`..." that talks about SQL output rather than meaning.

### Pitfall 2: Implying Databricks Users Should Not Use Fact

**What goes wrong:** A doc that leans too hard on "Databricks has no native fact concept" might lead Databricks users to conclude `Fact` is useless for them.

**Why it happens:** The warehouse divergence explanation highlights what Databricks lacks.

**How to avoid:** Frame it positively — `Fact` is still useful for Databricks users who want semantic precision in their models, even though the warehouse doesn't enforce it. The recommendation "default to Dimension, opt-in to Fact" applies equally to both audiences.

### Pitfall 3: Over-Explaining Star Schema

**What goes wrong:** The "Specific Ideas" section in CONTEXT.md mentions star schema as potentially useful context. This can become a multi-paragraph detour.

**Why it happens:** Star schema is a rich topic and easy to expand.

**How to avoid:** If referenced, one sentence maximum. E.g., "The name comes from star-schema terminology, where fact tables hold raw event measurements." If it doesn't naturally fit, omit it.

### Pitfall 4: Violating the Docs Quality Gate

**What goes wrong:** Markdown formatting errors, broken internal links, or invalid code fences fail `mkdocs build --strict`.

**How to avoid:** Run `uv run mkdocs build --strict` after edits.

## Code Examples

### Verified: Current Fact Field SQL Output (Identical to Dimension)

From `docs/src/how-to/models.md` (source: codebase inspection):

```python
class Orders(SemanticView, view="orders"):
    unit_price = Fact()
    quantity = Fact()
```

Snowflake:
```sql
SELECT "unit_price", "quantity"
FROM "orders"
GROUP BY ALL
```

Databricks:
```sql
SELECT `unit_price`, `quantity`
FROM `orders`
GROUP BY ALL
```

### Verified: Snowflake FACTS Clause Concept

From Snowflake official docs (fetched 2026-02-24):

- FACTS are row-level numeric attributes representing business events ("how much" or "how many" at granular levels)
- Facts "typically function as 'helper' concepts within the semantic view to help construct dimensions and metrics"
- Metrics aggregate facts; FACTS themselves are non-aggregated row-level values
- Distinction: FACTS = raw event-level numerics; DIMENSIONS = categorical context; METRICS = aggregated KPIs

Cubano's `Fact` class maps exactly to this: it's declared in the Python model for columns that correspond to Snowflake's `FACTS` clause.

### Verified: Databricks Has No Fact Concept

From Databricks official docs (fetched 2026-02-24):

- Databricks metric views have two field types: **dimensions** and **measures** (no fact type)
- Non-aggregated numeric columns that are used for grouping/filtering would be classified as `dimension:` in YAML
- The metric view YAML does not distinguish between categorical dimensions and numeric non-aggregated columns — both are `dimension:`
- Cubano's `Fact` provides a third classification absent from Databricks natively

### Example: Canonical Fact vs Dimension Column Names

Per CONTEXT.md (locked decision to include these inline):

- **Fact:** `unit_price`, `quantity`, `line_amount` — raw numerics from a fact/transaction table
- **Dimension:** `country`, `product_category`, `order_date` — categorical grouping attributes

## State of the Art

| Aspect | Current State | After Phase 19 |
|--------|--------------|----------------|
| Fact section prose | Thin (2 sentences, superficial) | Rich (warehouse divergence, when-to-use, canonical examples) |
| Snowflake alignment | Not mentioned | Explicitly linked to `FACTS` clause |
| Databricks guidance | Not mentioned | Explicit: no native fact concept, `Fact` is still useful for semantic precision |
| Default recommendation | Not stated | "Default to `Dimension`; `Fact` is intentional opt-in" |
| Comparison table | "Raw numeric values used in grouping or calculations" | Optionally updated to mention semantic intent |

## Open Questions

1. **Should `semantic-views.md` mention `Fact`?**
   - What we know: The page currently says "Python class with `Metric` and `Dimension` fields" — omits `Fact`
   - What's unclear: Whether one sentence ("Fact fields provide a third classification...") adds enough value to justify a touch
   - Recommendation: Add one sentence with a link to `models.md`. Low-effort, prevents the explanation page from implying the type system has only two types. This is Claude's discretion.

2. **Should the comparison table `Use for` cell be updated?**
   - What we know: Current text is accurate but thin
   - Recommendation: Update to something like "Raw event-level numeric columns (`unit_price`, `quantity`) — distinguishes from categorical `Dimension` fields." Low-effort, improves scannability.

## Validation Architecture

Nyquist validation is not enabled for this project. Skip.

## Sources

### Primary (HIGH confidence)

- Snowflake official docs, `docs.snowflake.com/en/sql-reference/sql/create-semantic-view` — FACTS clause syntax, semantics of FACTS vs DIMENSIONS
- Snowflake official docs, `docs.snowflake.com/en/user-guide/views-semantic/overview` — role of FACTS as row-level building blocks for metrics
- Databricks official docs, `docs.databricks.com/aws/en/metric-views/data-modeling/` — confirmed no native fact type; only dimensions and measures
- `/Users/paul/Documents/Dev/Personal/cubano/docs/src/how-to/models.md` — current state of `### Fact fields` section (lines 110–135)
- `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/fields.py` — `Fact` class definition (lines 630–638); confirms `Fact(Field)` with no runtime-special behavior
- `/Users/paul/Documents/Dev/Personal/cubano/docs/src/explanation/semantic-views.md` — current state; does not mention `Fact`

### Secondary (MEDIUM confidence)

- CONTEXT.md (phase 19) — all locked decisions, discretion areas, and deferred ideas (source of truth for scope)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — documentation-only phase, no new libraries
- Architecture: HIGH — clear existing pattern to follow in `models.md`; warehouse facts verified from official docs
- Pitfalls: HIGH — pitfalls identified from locked decisions in CONTEXT.md and codebase inspection

**Research date:** 2026-02-24
**Valid until:** 2026-05-24 (stable warehouse docs; Cubano codebase checked directly)
