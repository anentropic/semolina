---
status: resolved
trigger: "Diagnose root causes for UAT gaps 3, 4, 5 and meta concern about GSD plan docs"
created: 2026-02-22T00:00:00Z
updated: 2026-02-22T00:00:00Z
---

## Current Focus

hypothesis: confirmed - all three gaps share a common root cause chain
test: complete - read all source docs, planning files, summaries
expecting: n/a - diagnosis delivered
next_action: deliver structured root cause report

## Symptoms

expected: Home page uses end-user persona and byline. Installation tutorial hides venv tip from uv users. First query tutorial shows real warehouse usage, not MockEngine test fixture setup.
actual: Home page has LLM fluff and promotes MockEngine. Venv tip shown to all users. First query tutorial teaches users to load fixture data into MockEngine.
errors: none - content issues, not build failures
reproduction: read docs/src/index.md, docs/src/tutorials/installation.md, docs/src/tutorials/first-query.md
started: after phase 14 execution (plan 02)

## Eliminated

- hypothesis: plan tasks were not executed as written
  evidence: 14-02-SUMMARY.md says "None -- plan executed exactly as written." The files match the plan's instructions.
  timestamp: 2026-02-22

- hypothesis: the humanizer skill missed the issues
  evidence: tone issues (fluff text, promotion) are secondary to a structural requirement error; humanizer checks vocabulary patterns, not audience-appropriateness of the content chosen
  timestamp: 2026-02-22

## Evidence

- timestamp: 2026-02-22
  checked: 14-RESEARCH.md open question #3 about MockEngine runnability
  found: "What we know: User decided tutorials must have runnable code. The existing first-query.md already uses MockEngine for this." Explicitly framed MockEngine use as a settled decision.
  implication: The research phase locked in MockEngine as the tutorial approach without flagging it as a question of audience-appropriateness; it was treated as a technical runnability constraint.

- timestamp: 2026-02-22
  checked: 14-02-PLAN.md task 1 action, first-query.md specifics
  found: "Walk through: define a model, register a MockEngine, build a query, execute, read results" and "Code examples preserved from existing page"
  implication: Plan 02 explicitly instructed the executing agent to build the tutorial around MockEngine AND to preserve existing code. This made the wrong approach a plan requirement.

- timestamp: 2026-02-22
  checked: 14-02-SUMMARY.md key-decisions section
  found: "Tutorials use MockEngine for all runnable examples so readers don't need warehouse credentials"
  implication: The executing agent made this decision consciously and recorded it. The rationale ("don't need warehouse credentials") is a plausible but wrong tradeoff - it optimizes for zero-friction startup at the cost of teaching users the wrong workflow.

- timestamp: 2026-02-22
  checked: 14-CONTEXT.md decisions section - "Content depth & examples"
  found: "Tutorials: Runnable code -- works if pasted with right imports, show imports and output" and "Framing: User already has the semantic view; docs explain how Cubano mirrors/shadows it"
  implication: CONTEXT contradicts itself on tutorials: "user already has the semantic view" (real warehouse framing) BUT "runnable code" (which led to MockEngine). The plan never resolved this tension.

- timestamp: 2026-02-22
  checked: 14-02-PLAN.md task 1 action, installation.md specifics
  found: "Framing: 'You already have a semantic view in your warehouse. Cubano lets you query it from Python.'"
  implication: Installation tutorial was framed correctly in the plan. The venv tip issue is a content execution error, not a plan requirement error. The plan said nothing about conditionally showing venv advice.

- timestamp: 2026-02-22
  checked: docs/src/tutorials/installation.md lines 22-31
  found: "!!! tip 'Use a virtual environment'" appears outside any tab block, shown to all users regardless of uv vs pip selection
  implication: The executing agent did not think through the UX of showing pip-specific advice to uv users. The plan didn't specify this either - it was a detail left to execution judgment.

- timestamp: 2026-02-22
  checked: docs/src/tutorials/installation.md line 34
  found: "Cubano has zero runtime dependencies by default."
  implication: This claim is repeated from pre-phase content (the RESEARCH.md and MEMORY.md note "Core query engine has no runtime deps but this is not an enforced constraint"). The plan never flagged this as an inaccuracy to fix.

- timestamp: 2026-02-22
  checked: docs/src/index.md home page
  found: MockEngine in quick example code block on line 50: "register('default', MockEngine())" - this is the "preserved" quick example. Card description line 11: "Install Cubano and run your first query with a MockEngine."
  implication: Home page actively promotes MockEngine to users as the first-encounter narrative. This comes from two sources: (1) the preserved code example (plan said preserve it), (2) the card description written during plan execution.

- timestamp: 2026-02-22
  checked: 14-02-PLAN.md task 2, index.md update instructions
  found: "Keep the Quick Example code block unchanged" and "Consider adding a brief tagline that frames Cubano for the target audience"
  implication: The plan explicitly preserved the MockEngine quick example. The card description "run your first query with a MockEngine" was generated by the executing agent interpreting the first-query tutorial content, which is about MockEngine.

- timestamp: 2026-02-22
  checked: 14-CONTEXT.md for persona/byline requirements
  found: Audience defined as "Data/analytics engineers who already work with semantic views" but no specific byline or home page persona content requirements were specified. No mention of "Cubano: the ORM for your Semantic Layer" or equivalent positioning.
  implication: The byline gap is a requirements gap: the CONTEXT captured writing voice guidelines but did not specify the home page's positioning statement or marketing copy requirements.

## Resolution

root_cause: See structured diagnosis in delivery below.
fix: not in scope (diagnose only)
verification: n/a
files_changed: []
