# Phase 27: TOML Configuration & Real Pools - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning
**Source:** Inline conversation (assumptions review)

<domain>
## Phase Boundary

Phase 27 delivers `.semolina.toml` configuration loading and a `pool_from_config()` factory that creates real adbc-poolhouse pools from TOML config. Users define named connections with a `type` field, and `pool_from_config` returns a `(pool, Dialect)` tuple ready for `register()`.

</domain>

<decisions>
## Implementation Decisions

### TOML Format
- **Option B: flat with type field** — `[connections.name]` sections with `type = "snowflake"` field
- `type` field maps directly to `Dialect` enum values
- Each connection has a single warehouse type determining what credential keys are expected
- Multiple connections of the same type are supported (e.g. two snowflake connections)
- Format example:
  ```toml
  [connections.default]
  type = "snowflake"
  account = "xy12345"
  user = "myuser"

  [connections.analytics]
  type = "databricks"
  server_hostname = "xxx.cloud.databricks.com"
  http_path = "/sql/1.0/warehouses/abc"
  ```

### Config Loading Strategy
- **No pydantic-settings TomlConfigSettingsSource** — dropped as unnecessary complexity
- Parse `.semolina.toml` with `tomllib` directly in `pool_from_config`
- Pass parsed dict to adbc-poolhouse's own config classes (`SnowflakeConfig`, `DatabricksConfig`) directly
- No custom Semolina config wrapper classes (SnowflakePoolConfig etc.) — use adbc-poolhouse configs as-is

### pool_from_config API
- Returns `(pool, Dialect)` tuple — ready to register
- Signature: `pool_from_config(connection="default", config_path=".semolina.toml")`
- Reads named connection section, detects type, builds adbc-poolhouse config, creates pool

### Dependencies
- **adbc-poolhouse is a core dependency** (not optional extra)
- pydantic-settings is just a transitive dependency (comes via adbc-poolhouse)

### Claude's Discretion
- Whether to add adbc-driver-snowflake / adbc-driver-flightsql as optional extras in this phase
- How to handle env var overrides for credentials (adbc-poolhouse configs may have built-in env support)
- Whether existing `testing/credentials.py` coexists or gets updated
- Error handling for missing/invalid TOML sections

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 25/26 Implementation (source of truth for current state)
- `src/semolina/registry.py` — register() with pool+dialect, get_pool()
- `src/semolina/dialect.py` — Dialect StrEnum, resolve_dialect()
- `src/semolina/pool.py` — MockPool (for testing)

### Architecture Research
- `.planning/research/ARCHITECTURE.md` — v0.3 architecture design (config section 3.5)
- `.planning/research/STACK.md` — pydantic-settings TomlConfigSettingsSource analysis
- `.planning/phases/25-pool-registry-dialect-enum-mockpool/25-RESEARCH.md` — adbc-poolhouse confirmed real on PyPI v1.2.0

### Existing Config
- `.semolina.toml.example` — current flat format (needs updating to new connection format)

</canonical_refs>

<specifics>
## Specific Ideas

- adbc-poolhouse v1.2.0 provides `create_pool(config)` returning `sqlalchemy.pool.QueuePool`
- adbc-poolhouse provides typed configs: `SnowflakeConfig`, `DatabricksConfig`
- The `type` field in TOML maps to Dialect enum values ("snowflake", "databricks")

</specifics>

<deferred>
## Deferred Ideas

- Auto-registration (user still calls register() manually)
- Connection lifecycle management (pool cleanup, graceful shutdown)
- CLI integration with config
- Arrow-native fetch methods — Phase 28

</deferred>

---

*Phase: 27-toml-configuration-real-pools*
*Context gathered: 2026-03-17 via inline conversation*
