---
phase: 19-document-fact-field-type-for-databricks-and-snowflake-users
verified: 2026-02-24T00:00:00Z
status: passed
score: 6/6 must-haves verified
re_verification: false
human_verification:
  - test: "Read the expanded '### Fact fields' section end-to-end"
    expected: "Reading flow feels natural — warehouse divergence explains itself without being preachy or redundant with adjacent Dimension section"
    why_human: "Prose quality and reading flow cannot be assessed programmatically"
---

# Phase 19: Document Fact Field Type Verification Report

**Phase Goal:** Give Snowflake and Databricks users clear guidance on what `Fact` means in their warehouse context, when to use it vs `Dimension`, and what to expect at query time — by expanding the `### Fact fields` section in the models how-to guide.
**Verified:** 2026-02-24
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The `### Fact fields` section explains the Snowflake FACTS clause mapping explicitly | VERIFIED | Line 114-116: "The `Fact` type maps directly to the `FACTS` clause in your `CREATE SEMANTIC VIEW`. If a column is declared there, use `Fact` in your Cubano model — it is the direct Python counterpart." |
| 2 | The section explains that Databricks has no native fact concept and Fact is still useful there | VERIFIED | Lines 118-122: "Databricks metric views have no native fact concept...Use `Fact` in your Cubano model for raw numeric columns you want to distinguish semantically...the warehouse won't enforce the distinction, but your teammates and future readers will see the intent." |
| 3 | The section states clearly that Fact and Dimension produce identical SQL — the distinction is semantic only | VERIFIED | Lines 124-125: "At query time, `Fact` and `Dimension` produce identical SQL (`SELECT "col" FROM ... GROUP BY ALL`). The distinction is semantic, not a difference in execution." |
| 4 | The section recommends defaulting to Dimension with Fact as an intentional opt-in | VERIFIED | Line 127: "Default to `Dimension`. Use `Fact` as an intentional opt-in for two situations:" |
| 5 | Canonical examples of Fact vs Dimension columns are included (unit_price/quantity vs country/product_category) | VERIFIED | Lines 129-131 (prose): `unit_price`, `quantity`, `line_amount` as Fact examples, `country`, `product_category` as Dimension. Lines 137-140 (code): all four columns shown together in contrast snippet. |
| 6 | `uv run mkdocs build --strict` passes with no errors | VERIFIED | Build output: "Documentation built in 1.52 seconds" with zero warnings or errors |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/src/how-to/models.md` | Expanded `### Fact fields` section with warehouse divergence, when-to-use, and canonical examples | VERIFIED | Section expanded from 2 thin sentences to ~35 lines covering all required content. Contains "Snowflake users" at line 114. |
| `docs/src/how-to/models.md` | Updated comparison table Fact row with `unit_price` | VERIFIED | Line 55: `\| \`Fact\` \| Raw event-level numeric columns (\`unit_price\`, \`quantity\`) — signals semantic intent vs a categorical \`Dimension\` \| \`.dimensions()\` \|` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `docs/src/explanation/semantic-views.md` | `docs/src/how-to/models.md` | One-sentence Fact mention with link | VERIFIED | Lines 28-30: "A third field type, `Fact`, lets you mark raw event-level numerics separately from categorical dimensions — see [Defining models](../how-to/models.md)." Pattern "Fact" present in the "Where Cubano fits" section. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DOCS-04 | 19-01-PLAN.md | "Query language guide: Q-objects and AND/OR composition" (REQUIREMENTS.md) | MISMATCH — see note below | Phase 19 work is Fact field documentation, not Q-objects. DOCS-04 was already completed by Phase 10/15. |

**Requirement ID Mismatch — DOCS-04:**

The PLAN frontmatter claims `requirements: [DOCS-04]`, but DOCS-04 in REQUIREMENTS.md is defined as "Query language guide: Q-objects and AND/OR composition" — work completed in Phase 10 and Phase 15. Phase 19's actual work (documenting the `Fact` field type for Snowflake/Databricks users) is not captured by any existing requirement ID in REQUIREMENTS.md, and Phase 19 does not appear in the REQUIREMENTS.md traceability table.

**Assessment:** The implementation work is correct and complete — the documentation changes fully achieve the phase goal. The issue is administrative: the requirement ID in the PLAN frontmatter does not correspond to what Phase 19 actually delivers, and the traceability table in REQUIREMENTS.md does not list Phase 19. This is a bookkeeping gap, not a content gap. The underlying documentation goal is fully achieved.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

No TODO/FIXME/placeholder comments, no empty implementations, no promotional language, no AI vocabulary detected in the modified files.

### Human Verification Required

#### 1. Reading Flow Check

**Test:** Read `docs/src/how-to/models.md` from the `### Fact fields` heading (line 110) through to the end of the tabbed SQL block (line 157).
**Expected:** The warehouse divergence paragraphs (Snowflake / Databricks) feel like natural reading flow, not an interruption. The "identical SQL" note lands cleanly after the divergence. The code snippet with Fact + Dimension contrast at lines 136-157 reinforces the prose rather than repeating it.
**Why human:** Prose quality, reading flow, and conceptual clarity cannot be assessed programmatically.

### Gaps Summary

No gaps blocking goal achievement. All six must-have truths are verified:

- Snowflake FACTS clause mapping: explicitly stated
- Databricks no-native-fact explanation: present and positively framed (semantic utility acknowledged)
- Identical SQL statement: present and clear
- "Default to Dimension" recommendation: explicit opt-in framing
- Canonical column examples: in both prose and code
- mkdocs build: passes with no errors

The only finding is a bookkeeping mismatch — DOCS-04 in the PLAN frontmatter does not correspond to Phase 19's actual content. This does not affect goal achievement; the documentation changes fully deliver what the phase goal specifies. The traceability table in REQUIREMENTS.md should be updated to include Phase 19 and associate it with the correct documentation improvement work if precise traceability is important.

---

_Verified: 2026-02-24_
_Verifier: Claude (gsd-verifier)_
