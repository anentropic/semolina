# Gap Detection Report

**Source root:** src/
**Language:** python
**Docs scanned:** 30 `.rst` pages under `docs/src/` (excluding the sphinx-autoapi output at
`docs/src/reference/api/`, which is generated at build time and not checked in)

**Public API symbols (the three `__all__` lists):** 36
**Mentioned in hand-written prose:** 34 (94%)
**Not mentioned anywhere:** 2

## Undocumented exports

| Symbol | File | Type | Note |
|--------|------|------|------|
| `DialectABC` | `src/semolina/engines/sql.py` | class (re-exported as `DialectABC`) | Exported from `semolina.engines`, named in no page. Its three concrete subclasses are all named. |
| `DuckDBDialect` | `src/semolina/engines/duckdb.py` | class | `SnowflakeDialect` and `DatabricksDialect` both appear in `how-to/dto-codegen.rst` provenance-header examples; the DuckDB one does not, purely because the examples chose the other two. |

Both are low-severity. Neither is a symbol a reader constructs directly — a dialect arrives
attached to an `Engine` built by `create_engine()` — and both carry docstrings, so both are
covered by the generated API reference. The gap is prose, not reference.

## New in this change set

The `--view` / `pyproject.toml` work added symbols that are **not** in any `__all__` and are
therefore outside the public-API count above:

| Symbol | File | Covered by |
|--------|------|-----------|
| `build_query` | `src/semolina/codegen/query_resolver.py` | autoapi + `how-to/dto-codegen.rst` (CLI surface) |
| `ad_hoc_origin` | `src/semolina/codegen/query_resolver.py` | autoapi |
| `is_valid_field_name` | `src/semolina/codegen/query_resolver.py` | autoapi |
| `load_dto_config` | `src/semolina/codegen/dto_config.py` | autoapi + `how-to/dto-codegen.rst`, `reference/cli.rst` |
| `DtoConfig`, `DtoEntry` | `src/semolina/codegen/dto_config.py` | autoapi |
| `SECTION`, `ENTRIES_SECTION`, `DEFAULT_CONFIG_FILE` | `src/semolina/codegen/dto_config.py` | autoapi |

These sit alongside `resolve_query`, `class_name_for` and `projection_only`, which have the
same treatment: docstrings picked up by autoapi, with the user-facing behaviour documented
through the CLI rather than as a library API. Consistent with what was already there.

## Notes

- The `codegen` package (`type_map`, `arrow_map`, `introspector`, `probe`, `python_renderer`,
  `dto_renderer`, `annotation_check`, `model_reader`) is internal machinery reached through
  the two CLI commands. None of it is in `__all__`, and none of it has hand-written prose.
  That is deliberate and not counted as a gap.
- `src/semolina/conftest.py` defines a `Sales` model used for doctest setup. The export
  scanner reports it as a public class; it is a test fixture and should be ignored.
- `cli/utils.py` exports `make_stderr_console` and `resolve_input_paths`. `resolve_input_paths`
  is not called by either shipped command — worth a look as possible dead code, though that is
  a source question rather than a docs one.
