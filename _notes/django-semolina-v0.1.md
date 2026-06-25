# django-semolina v0.1 — Scope Sketch

**Status:** Shelved. Will live in a separate repo / project — not part of Semolina v0.5.
**Captured:** 2026-05-14
**Source:** New-milestone discussion for Semolina v0.5; predecessor todo `2026-02-18-django-cubano-wrapper.md`.

## What it is

A Django integration helper package that makes Semolina feel native to Django projects — settings-based configuration, AppConfig lifecycle, and a codegen management command.

Lives in its own repo (`django-semolina` or similar), pip-installable as `django-semolina`. Depends on `semolina` and `django`. Not part of the Semolina monorepo.

## v0.1 Scope (the three confirmed features)

1. **`SEMOLINA` settings dict in `settings.py`** — Django-style config block, modelled on Django's `DATABASES`. Each entry describes a named pool (type, connection params, dialect).

   ```python
   # settings.py
   SEMOLINA = {
       "default": {
           "type": "snowflake",
           "account": "...",
           "user": "...",
           # ...
       },
       "analytics": {
           "type": "duckdb",
           "database": "/var/data/warehouse.db",
       },
   }
   ```

2. **`AppConfig.ready()` auto-registers pools from settings** — On app startup, iterate `settings.SEMOLINA` and call the equivalent of `semolina.register(name, pool, dialect=...)` for each entry. Use `pool_from_config()` semantics under the hood so the settings dict mirrors `.semolina.toml` keys.

3. **Codegen management command** — `./manage.py semolina_codegen sales` introspects a warehouse view and writes a Python model file. Wraps the existing `semolina codegen` CLI, but routes connection params through the `SEMOLINA` settings dict (no need to re-supply credentials on the CLI).

## Out of scope for v0.1

Captured during discussion, deferred to later django-semolina milestones:

- DRF serializer / renderer for `SemolinaCursor` / `Row` → JSON
- Arrow IPC streaming HTTP response (depends on Semolina STREAM-01/02 landing first)
- Django admin view for browsing registered semantic views
- Async / ASGI view helpers
- `Model.query()`-style Django manager pattern (vs. thin glue)

## Dependencies on Semolina

- `pool_from_config()` from Semolina v0.3 — already exists, usable as-is
- `semolina codegen` CLI from Semolina v0.2 (Snowflake/Databricks) / v0.4.0 (DuckDB) — already exists
- No new extension points required from Semolina core for v0.1

If later django-semolina milestones add Arrow IPC streaming, that work depends on Semolina `STREAM-01/02` (slated for v0.5).

## When to resume

After Semolina v0.5 ships (STREAM-01/02, DKGEN-04). The Arrow streaming work in v0.5 unlocks the most interesting Django-side feature (Arrow IPC → HTTP), even though that's a v0.2+ feature of django-semolina, not v0.1.

## Original todo reference

`.planning/todos/pending/2026-02-18-django-cubano-wrapper.md` — predates the `cubano → semolina` rename. The names in the original todo (`CUBANO`, `cubano.register()`, `CubanoAppConfig`) should be read as `SEMOLINA`, `semolina.register()`, `SemolinaAppConfig`.
