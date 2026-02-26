---
created: 2026-02-19T17:45:34.345Z
title: Support all auth schemes for each backend provider
area: api
files:
  - src/cubano/testing/credentials.py
  - src/cubano/backends/snowflake.py
  - src/cubano/backends/databricks.py
---

## Problem

Currently `SnowflakeCredentials` only supports username/password auth. The Snowflake connector supports multiple auth methods:
- Username/password (current)
- SSO (`authenticator = "externalbrowser"`)
- OAuth / key-pair (`authenticator = "snowflake_jwt"`, `private_key_path`)
- Okta / SAML (`authenticator = "https://..."`)

Similarly, Databricks supports:
- Personal Access Token (current)
- OAuth M2M (`client_id` + `client_secret`)
- External token providers

The `.cubano.toml` example already hints at these (commented-out fields in `scripts/connections.toml.example`) but neither `SnowflakeCredentials`, `DatabricksCredentials`, nor the engine constructors model or pass these through.

## Solution

Extend `SnowflakeCredentials` and `DatabricksCredentials` in `testing/credentials.py` with optional auth fields (all `str | None = None`):
- Snowflake: `authenticator`, `private_key_path`, `private_key_passphrase`
- Databricks: `client_id`, `client_secret`

Update `SnowflakeEngine` and `DatabricksEngine` to pass these through to the connector when non-None. Consider a small `auth_kwargs()` helper method on each credentials model that returns only the non-None auth fields as a dict for clean `**kwargs` spreading.

Ensure `.cubano.toml` `[snowflake]`/`[databricks]` sections accept these fields (already works since pydantic-settings `extra="ignore"` handles unknown keys gracefully — but we want to include them).
