# API Coverage — Phase 48

No external API integration: this phase changes Semolina's internal type-mapping tables, its SQL
literal renderer, and adds a `--check` flag to an existing CLI command — it integrates no external
API, SDK, or service.

## Why the detector fired

The `api-coverage` detector reported `detected: true` on the signal `{verb: "consumes", noun: "api"}`.
That pairing comes from `48-04-PLAN.md:290`, which reads:

> "The module path and exported names become public **API** that Phase 50's DTO-07 **consumes**."

That sentence is about **Semolina's own public surface** — `semolina.codegen.probe.probe_schema` and
`semolina.codegen.arrow_map.arrow_type_to_python` becoming importable by a later phase of this same
project. It is not an integration against a third-party API.

Re-read of the phase scope confirms it, per the capability's own instruction to confirm by reading
rather than by preference:

- **What the phase touches:** `src/semolina/codegen/type_map.py`, `arrow_map.py`, `probe.py`,
  `model_reader.py`, `annotation_check.py`, `python_renderer.py`, its Jinja template,
  `src/semolina/engines/sql.py`, `src/semolina/cli/`, `src/semolina/types.py`, and two docs pages.
- **Dependency delta:** none. `git diff 9f3c8b9..HEAD -- pyproject.toml uv.lock` is empty — no
  package was added, so no new vendor surface entered the project.
- **Warehouse access is pre-existing.** The ADBC drivers this phase reads schemas through were
  integrated in v0.6 (Engine architecture) and Phases 44–45. Phase 48 adds no connection path, no
  endpoint, and no new driver capability — `adbc_execute_schema` was already in use from Phase 47's
  type-fidelity probe, which this phase promoted out of `tests/` into `src/` unchanged.

No capability matrix is produced because there is no external capability surface to enumerate.
Fabricating rows here would record decisions about endpoints that do not exist.

## Not to be confused with the phase's real evidence limits

This phase does carry documented gaps, but they are measurement gaps rather than coverage
decisions, and they live in their own ledger:

| Limit | Where it is recorded |
|---|---|
| Databricks `interval` unmapped (TYPE-05 partial) | WINDOWS.md entry 7 + `.planning/todos/pending/2026-08-12-record-databricks-interval-column.md` |
| `VARIANT` → `JsonValue` unmeasured | WINDOWS.md entry 8 |
| `--check` unclaimed on Databricks; Snowflake comparison-core only | WINDOWS.md entries 2 and 9 |

Each names the recording session that would close it. None is an un-decided API hole.
