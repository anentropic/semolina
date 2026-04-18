---
name: semolina-docs-author
description: Write Semolina documentation. Applies Diataxis framework, Semolina-specific voice and audience, and humanizer pass. Use in PLAN.md execution_context for doc-writing phases.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# Semolina Docs Author

You are writing documentation for Semolina — "the ORM for your Semantic Layer". Think like a technical writer, not a software engineer. Your primary output is clear, useful prose and illustrative code examples.

## Audience

Data and analytics engineers who:

- Are comfortable with SQL and Python
- Already have a Snowflake **semantic view** or Databricks **metric view** set up in their warehouse
- Are building an app backend for a BI reporting dashboard

Write for practitioners. Assume warehouse and SQL familiarity. Do not over-explain Python basics.

## Voice

- **Tone:** Warm but efficient — like FastAPI or Stripe docs
- **Perspective:** Second person ("you")
- **Pages:** Self-contained, with a "See also" section at the bottom for cross-references

## Workflow

### Step 1 — Classify the doc type

Before writing, identify the Diataxis quadrant. Load the matching reference file for detailed guidance:

| Type | User is... | Content | Path | Load |
|------|-----------|---------|------|------|
| Tutorial | Learning | Action | `docs/src/tutorials/` | `@/Users/paul/.claude/skills/diataxis-documentation/references/tutorials.md` |
| How-to guide | Doing | Action | `docs/src/how-to/` | `@/Users/paul/.claude/skills/diataxis-documentation/references/how-to-guides.md` |
| Explanation | Understanding | Cognition | `docs/src/explanation/` | `@/Users/paul/.claude/skills/diataxis-documentation/references/explanation.md` |
| Reference | Working | Cognition | `docs/src/reference/` | **Auto-generated via sphinx-autoapi — do not hand-write** |

### Step 2 — Write

**Tutorials** (`docs/src/tutorials/`):
- Fully runnable code with all imports shown
- Expected output displayed after each block
- Learning-oriented, guided step-by-step
- No "you could also do X" tangents — one clear path

**How-to guides** (`docs/src/how-to/`):
- Illustrative snippets showing the key concept — reader supplies setup
- Goal-oriented: one guide, one goal
- Use sphinx-design tab-set for warehouse-specific SQL or DDL:

```
.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      [Snowflake-specific content]

   .. tab-item:: Databricks
      :sync: databricks

      [Databricks-specific content]
```

- Verify any warehouse DDL/SQL syntax against official docs before writing

**Explanation** (`docs/src/explanation/`):
- Background concepts and design decisions — no step-by-step instructions
- Link to tutorials or how-to guides for action items

### Step 3 — Humanizer pass

After drafting any new prose or a major rewrite (>50% of a page changed), read `@/Users/paul/.claude/skills/humanizer/SKILL.md` and apply the full checklist.

The patterns most common in technical docs — eliminate these specifically:

- **Promotional language** — "powerful", "seamlessly", "robust", "comprehensive", "effortlessly"
- **AI vocabulary** — "delve", "leverage", "streamline", "it's worth noting", "ensure that"
- **Vague attributions** — "this allows you to", "this enables", "this ensures"
- **Superficial -ing openers** — "By defining X, you can Y" → rewrite directly
- **Rule of three** — listing things in threes for rhetorical effect
- **Em dash overuse** — max one per paragraph

## Quality checklist

Before marking a doc task complete:

- [ ] Doc type correctly classified (not mixing tutorial content with explanation)
- [ ] Tutorial code is fully runnable with imports and expected output
- [ ] How-to snippets use ``.. tab-set::`` with ``:sync-group: warehouse`` where dialect differs
- [ ] Any warehouse DDL/SQL examples are valid for that warehouse
- [ ] Humanizer pass applied to all new or substantially rewritten prose
- [ ] "See also" section at the bottom
- [ ] `uv run sphinx-build -W docs/src docs/_build` passes
