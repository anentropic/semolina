# Phase 44: Engine Owns the Pool (SQLAlchemy-Style) - Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 11 source modules + 7 test modules (all MODIFIED; `create_engine` is the one new symbol, added inside an existing file)
**Analogs found:** 11 / 11 (every new behavior has an in-repo analog; only the Databricks ADBC-introspect path is spike-gated, not analog-gated)

> This is a refactor. RESEARCH.md already maps current signatures and call patterns;
> this file does NOT repeat that. It assigns each touch-point its **closest in-repo
> analog** and pins the **exact lines to copy from**. Read this alongside 44-RESEARCH.md
> (the two are complementary: research = "what/why + verified signatures", patterns =
> "which existing code to mirror, line-by-line").

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `config.py` — `create_engine()` (NEW) | config / factory | request-response (build) | `config.py::pool_from_config` (same file, lines 61-126) | exact (same dispatch shape) |
| `config.py` — type→dialect reverse lookup | config / mapping | transform | `config.py::_CONFIG_MAP` (lines 24-28) | exact |
| `engines/base.py` — `Engine` ABC (own pool+dialect, add `connect()`, drop `to_sql`) | model / ABC | — | `engines/base.py` current ABC (lines 27-161) + `registry.py` pool ownership | role-match |
| `engines/snowflake.py` — `execute()` rewrite (ADBC) | service | request-response | `query.py::_Query.execute` (lines 414-427) | exact (the canonical ADBC checkout path) |
| `engines/snowflake.py` — `introspect()` (native→ADBC) | service | request-response (introspect) | self (lines 323-380) + ADBC cursor pattern from `query.py:423-425` | exact (swap conn only) |
| `engines/duckdb.py` — `introspect()` (native duckdb→pool) | service | request-response (introspect) | `duckdb.py` current (lines 196-287) + `conftest.py::duckdb_pool` (lines 107-133) | exact |
| `engines/databricks.py` — `introspect()` (native→ADBC) | service | request-response (introspect) | `snowflake.py` introspect ADBC rewrite (sibling) | role-match (SPIKE-gated) |
| `registry.py` — `register(name, engine)` / `get_engine` | utility / registry | CRUD (in-mem map) | `registry.py` current (lines 18-115) | exact (collapse tuple→Engine) |
| `query.py` — `execute()`/`using()` resolution | service | request-response | `query.py::execute` current (lines 414-427) | exact (rename `get_pool`→`get_engine`) |
| `cli/codegen.py` — `_resolve_backend()` | controller / CLI | request-response | `cli/codegen.py` current (lines 65-138) | exact (collapse 3 branches → `create_engine`) |
| `__init__.py` — public surface | config / exports | — | `__init__.py` current (lines 8-38) | exact |
| `tests/unit/test_registry.py` | test | — | self (3-arg `register` calls) | exact (rewrite to 2-arg) |
| `tests/unit/test_pool.py` | test | — | `test_pool.py::TestExecuteWithPool` (lines 207-271) | exact |
| `tests/unit/test_snowflake_engine.py` | test | — | `test_pool.py` real-pool cursor asserts (lines 33-67) for ADBC-cursor mocking | role-match (native mock → ADBC mock) |
| `tests/unit/test_duckdb_engine.py` | test | — | `conftest.py::duckdb_pool` (lines 107-133) | exact (introspect over a real pool) |
| `tests/unit/test_databricks_engine.py` | test | — | snowflake-engine ADBC mock rewrite (sibling) | role-match (SPIKE-gated) |
| `tests/conftest.py` / `src/semolina/conftest.py` | test fixture | — | `conftest.py::duckdb_pool` (lines 107-133) | exact (register pool→engine) |
| `tests/integration/conftest.py` | test fixture | — | `tests/integration/conftest.py` (lines 82-177) | exact (create_pool+register → create_engine+register) |

---

## Pattern Assignments

### `config.py::create_engine()` — NEW (config, factory)

**Analog:** `config.py::pool_from_config` (same file). `create_engine` IS `pool_from_config`
plus the config-object branch, returning an `Engine` instead of `(pool, dialect)`. Copy the
TOML read verbatim; fold `pool_from_config` into the str-name branch (CONTEXT decision 5).

**TOML-read + type-dispatch to copy** (`config.py:93-126`):
```python
path = Path(config_path)
with path.open("rb") as f:
    config = tomllib.load(f)
connections: dict[str, Any] = config.get("connections", {})
if connection not in connections:
    available = list(connections.keys())
    raise KeyError(f"Connection '{connection}' not found in {config_path}. ...")
section = dict(connections[connection])
conn_type = section.pop("type", None)
if conn_type is None:
    raise ValueError(f"Connection '{connection}' ... is missing required 'type' field ...")
if conn_type not in _CONFIG_MAP:
    raise ValueError(f"Unsupported connection type '{conn_type}'. ...")
config_cls, dialect = _CONFIG_MAP[conn_type]
wh_config = _expand_private_key_path(config_cls(**section))
pool = create_pool(wh_config)
if conn_type == "duckdb":                       # MUST preserve — see Shared Pattern: DuckDB extension
    from sqlalchemy import event
    event.listen(pool, "connect", _load_semantic_views)
return pool, dialect                             # CHANGES: build + return an Engine
```

**Config-object branch (the NEW half)** — reverse-map `type(config) → Dialect` off `_CONFIG_MAP`
so it stays in sync (`config.py:24-28`):
```python
_CONFIG_MAP: dict[str, tuple[type, Dialect]] = {
    "snowflake": (SnowflakeConfig, Dialect.SNOWFLAKE),
    "databricks": (DatabricksConfig, Dialect.DATABRICKS),
    "duckdb": (DuckDBConfig, Dialect.DUCKDB),
}
# new reverse lookup (build once): {SnowflakeConfig: Dialect.SNOWFLAKE, ...}
```
Dispatch (per RESEARCH Pattern 3): `isinstance(config, str)` → TOML branch (folded
`pool_from_config`); else config-object branch (`type(config)` reverse lookup). poolhouse
configs are pydantic `BaseSettings`, never `str`, so the discriminator is safe.

**Disposition of siblings in this file:** DELETE `snowflake_connect_kwargs` (`config.py:177-216`)
and `databricks_connect_kwargs` (`config.py:219-243`) — but only AFTER their two consumers
(`cli/codegen.py:89,99,103,113` and `tests/integration/conftest.py`) stop importing them, or
basedpyright/imports break (RESEARCH "Deprecated/outdated"). Keep `_expand_private_key_path`,
`_load_semantic_views`, `warehouse_config` (still used by CLI/fixtures).

---

### `engines/base.py::Engine` ABC (model / ABC)

**Analog:** current ABC (lines 27-161) for what to keep; `registry.py` for the pool+dialect
ownership being absorbed into the base.

**Change shape (CONTEXT decision 2, RESEARCH "Recommended Structure"):**
- The base now **stores** `pool` + `dialect` (today only subclasses hold a `dialect`;
  `SnowflakeEngine.__init__` sets `self.dialect = SnowflakeDialect()` at `snowflake.py:151`).
  Move that to a base `__init__(self, *, pool, dialect)`.
- ADD `connect()` → `self._pool.connect()` (the SQLAlchemy parallel; checkout authority).
- DROP the abstract `to_sql()` (lines 57-90) — CONTEXT "lean drop", redundant with
  `Query.to_sql()`. Planner MAY keep a thin delegator only if cheap.
- KEEP abstract `introspect()` (lines 132-161) and `execute()` (lines 92-130) — but `execute()`
  is no longer native; see snowflake `execute()` rewrite below.

**Error classes stay** (`base.py:19-24`) — `SemolinaViewNotFoundError`,
`SemolinaConnectionError`. The introspectors must keep raising these, only the *caught* error
type changes (native → `adbc_driver_manager.Error`, RESEARCH Code Examples note).

---

### `engines/snowflake.py::execute()` — REWRITE on ADBC (service, request-response)

**Analog:** `query.py::_Query.execute` (lines 414-427). This is THE canonical poolhouse
checkout + `SemolinaCursor` path. The current `SnowflakeEngine.execute` (`snowflake.py:229-262`,
native `snowflake.connector.connect` + `%s`) is **broken** (qmark mismatch) — do NOT carry it
forward (RESEARCH Pitfall 4). Replace its body with this shape:

**Pattern to mirror** (`query.py:414-427`):
```python
from .cursor import SemolinaCursor
from .registry import get_pool                    # in Engine.execute, no registry — use self
self._validate_for_execution()
pool, dialect = get_pool(self._using)             # Engine already owns: self._pool, self.dialect
builder = dialect.create_builder()
sql, params = builder.build_select_with_params(self)
conn = pool.connect()                             # → self._pool.connect() (or self.connect())
cur = conn.cursor()
cur.execute(sql, params)                          # qmark params — ADBC-compatible
return SemolinaCursor(cur, conn, pool)            # pass real conn + pool for reset-event cleanup
```
`SemolinaCursor.__init__(cursor, conn, pool)` (`cursor.py:30-47`) needs `conn` + `pool` for
lifecycle/Arrow-reset on checkin (RESEARCH Pitfall 3). When the Engine owns the pool, pass
`self._pool` (expose it or a property) so `_release_arrow_allocators` still fires.

> NOTE: `execute()` becomes backend-agnostic (it's just pool checkout + builder + cursor). The
> planner may lift it to `engines/base.py` rather than reimplement per subclass — the only
> backend-specific bit is `self.dialect.create_builder()`, already a dialect method.

---

### `engines/snowflake.py::introspect()` — native conn → ADBC cursor (service, introspect)

**Analog:** itself (lines 323-380) — **SQL and parsing are unchanged** (live-spike proven,
CONTEXT decision 3; identical 13-col result over ADBC). Only the connection source and the
caught error classes change.

**Current (native — the swap target)** (`snowflake.py:324-328`):
```python
with (
    snowflake.connector.connect(**self._connection_params) as conn,   # ← REPLACE
    conn.cursor() as cur,
):
    cur.execute(f"SHOW COLUMNS IN VIEW {qualified_name}")             # SQL UNCHANGED
    columns = [desc[0].lower() for desc in cur.description]
    for row in cur.fetchall():
        ...                                                           # parser block 333-364 UNCHANGED
```

**New (ADBC checkout — mirror `query.py:423-425`):**
```python
with self.connect() as conn:                      # Engine.connect() → self._pool.connect()
    cur = conn.cursor()
    cur.execute(f"SHOW COLUMNS IN VIEW {qualified_name}")
    columns = [desc[0].lower() for desc in cur.description]
    ...
```

**PRESERVE the db-qualification logic** (`snowflake.py:317-321`) — RESEARCH anti-pattern: do not
hand-re-quote; keep the `< 3 parts → prepend database` prefix. Today it reads
`self._connection_params['database']`; after the rewrite the database lives on the poolhouse
`SnowflakeConfig` the Engine holds — read it from there (e.g. `self._config.database`).

**Error translation changes** (`snowflake.py:372-380`): today catches
`snowflake.connector.errors.{ProgrammingError,DatabaseError}`. Over ADBC catch
`adbc_driver_manager.Error` subclasses (PEP-249) and still raise
`SemolinaViewNotFoundError` / `SemolinaConnectionError` (RESEARCH Code Examples note).

---

### `engines/duckdb.py::introspect()` — native duckdb → pool (service, introspect)

**Analog:** current `duckdb.py` introspect (lines 196-287) for the two-pass SQL + parser
(UNCHANGED), and `conftest.py::duckdb_pool` (lines 107-133) for **how the extension is loaded
on a pooled connection** instead of per-call.

**Current (native, per-call INSTALL/LOAD — the swap target)** (`duckdb.py:198-202`):
```python
conn = duckdb.connect(database=self._database, read_only=True)
conn.execute("INSTALL semantic_views FROM community")     # ← moves to the pool connect-event
conn.execute("LOAD semantic_views")
result = conn.execute(f"DESCRIBE SEMANTIC VIEW {unqualified}")   # SQL + parser UNCHANGED (202-271)
```

**New — extension load moves to the pool's connect event** (`conftest.py:121-125`,
`config.py:31-43`):
```python
from semolina.config import _load_semantic_views
event.listen(pool, "connect", _load_semantic_views)       # done in create_engine for DuckDBConfig
# then introspect just checks out:
with self.connect() as conn:
    cur = conn.cursor()
    cur.execute(f"DESCRIBE SEMANTIC VIEW {unqualified}")  # unchanged
```
`read_only=True` intent maps to `DuckDBConfig(read_only=True)` (RESEARCH DuckDB note). Keep the
DuckDB error mapping (`duckdb.py:273-283`) translated to ADBC error classes, same as Snowflake.

---

### `engines/databricks.py::introspect()` — native → ADBC (service, introspect, SPIKE-GATED)

**Analog:** the Snowflake introspect ADBC rewrite (sibling). Same swap: replace
`databricks.sql.connect(**self._connection_params)` (`databricks.py:326-330`) with
`self.connect()`; keep `DESCRIBE TABLE EXTENDED {view_name} AS JSON` + the JSON parser
(`databricks.py:330-360`) unchanged; re-target the `except` clauses (`databricks.py:362-375`)
from `databricks.sql.exc.*` to ADBC errors.

**BLOCKER (RESEARCH Pitfall 5 + A2):** the Foundry Databricks ADBC driver is NOT installed and
NOT on PyPI. The spike's first sub-task is driver acquisition. Fallback: ship Snowflake+DuckDB
on the new API; leave a marked `NotImplementedError`/TODO here. Plan must gate this behind the
spike, not block the milestone.

---

### `registry.py` — `register(name, engine)` / `get_engine` (utility, registry)

**Analog:** current `registry.py` (lines 18-115). Collapse the `(pool, dialect)` tuple to a
single `Engine` (which carries both). Clean break, 2-arg `register` (CONTEXT decision 4).

- `_pools: dict[str, tuple[Any, DialectABC]]` (line 18) → `_engines: dict[str, Engine]`.
- `register(name, pool, *, dialect)` (lines 22-54) → `register(name, engine)` (drop `dialect`,
  drop `resolve_dialect`). Keep the duplicate-name guard (lines 51-52).
- `get_pool(name) -> tuple[pool, dialect]` (lines 57-87) → `get_engine(name) -> Engine`
  (RESEARCH Open Q2 recommendation: rename). Keep the "available names" error formatting.
- `reset()` (lines 99-115): the `close_pool`/`_adbc_source` cleanup now reaches the pool **via**
  the engine (`engine._pool`); keep the same `close_pool` call.

---

### `query.py::execute()` / `using()` (service, request-response)

**Analog:** current `execute()` (lines 414-427) — the same body, but resolve an Engine:
```python
# from .registry import get_pool        →  from .registry import get_engine
pool, dialect = get_pool(self._using)   →  engine = get_engine(self._using)
builder = dialect.create_builder()      →  builder = engine.dialect.create_builder()
conn = pool.connect()                   →  conn = engine.connect()
...
return SemolinaCursor(cur, conn, pool)  →  return SemolinaCursor(cur, conn, engine._pool)
```
Equivalently, delegate the whole body to `engine.execute(self)` (preferred — keeps the
checkout in one place; RESEARCH anti-pattern: don't reach into `engine._pool` from `query`
beyond what `SemolinaCursor` needs).

---

### `cli/codegen.py::_resolve_backend()` (controller / CLI)

**Analog:** current `_resolve_backend` (lines 65-138). Today it has three near-identical branches
that build native kwargs (`snowflake_connect_kwargs(warehouse_config("snowflake"))` etc., lines
86-122). Collapse to: `config = warehouse_config(backend)` → `Engine = create_engine(config)`.
This DELETES the `snowflake_connect_kwargs` / `databricks_connect_kwargs` imports (lines 89,103)
— a prerequisite for deleting those helpers in `config.py`. Keep the `typer.BadParameter`
ValidationError handling (lines 92-98) and the dotted-import custom-engine escape hatch
(lines 123-137).

---

### `__init__.py` — public surface (config / exports)

**Analog:** current `__init__.py` (lines 8-38). Per CONTEXT decision 5:
- ADD `create_engine` import + `__all__` entry.
- KEEP `register`, `unregister`; `get_pool` → `get_engine` (line 15, 34).
- DROP `pool_from_config` export (lines 8, 35) — internal-only after the fold.
- Per-backend `Engine` subclasses stay un-exported (internal, selected by `create_engine`).
- Keep `SemolinaConnectionError` / `SemolinaViewNotFoundError`, `SemanticView`, fields, `Row`.

---

## Shared Patterns

### ADBC pool checkout + SemolinaCursor (the one true execution path)
**Source:** `query.py:414-427` (current) + `cursor.py:30-47` (lifecycle contract)
**Apply to:** `Engine.execute()` (base or per-subclass), `query.execute()`, every introspector.
```python
conn = pool.connect()          # pooled ADBC DBAPI connection
cur = conn.cursor()
cur.execute(sql, params)       # qmark (?) params — all backends, post-799a8b0
return SemolinaCursor(cur, conn, pool)   # conn+pool required for reset-event Arrow cleanup
```

### DuckDB `semantic_views` extension load (connect-event, not per-call)
**Source:** `config.py:31-43` (`_load_semantic_views`) + `conftest.py:121-125` (the `event.listen`)
**Apply to:** `create_engine` whenever config is `DuckDBConfig`. Forgetting this → "Catalog
Error"/unknown `semantic_view` only on DuckDB (RESEARCH Pitfall 2). `create_engine` MUST
replicate the branch `pool_from_config` does at `config.py:121-124`.

### Error translation (warehouse-native → Semolina error classes)
**Source:** `engines/base.py:19-24` (the classes) + each introspector's `except` block
**Apply to:** all introspectors. Pattern is unchanged (raise `SemolinaViewNotFoundError` /
`SemolinaConnectionError`); only the **caught** type moves from native
(`snowflake.connector.errors.*`, `databricks.sql.exc.*`, `duckdb.*`) to
`adbc_driver_manager.Error` subclasses (PEP-249).

### Pool teardown
**Source:** `registry.py:99-115` + `conftest.py:133` (`close_pool(pool)`)
**Apply to:** `registry.reset()` and every fixture teardown. Use `adbc_poolhouse.close_pool`,
not bare `pool.dispose()` (closes the `_adbc_source`; RESEARCH "Don't Hand-Roll").

### Test-mock rewrite: native `sys.modules` mock → ADBC cursor mock
**Source (what to delete):** `test_snowflake_engine.py:47-76` — the autouse
`_mock_snowflake_in_sys_modules` fixture stubbing `snowflake.connector` + a
`mock_cursor.description`/`mock_cursor.fetchall` MagicMock (lines 232-235).
**Source (analog to mirror):** the real-pool cursor contract in `test_pool.py:41-58`
(`conn.cursor()`, `cur.execute(...)`, `cur.description`, `cur.fetchall()`) and the real-pool
introspect approach in `conftest.py::duckdb_pool` (107-133).
**Apply to:** `test_snowflake_engine.py`, `test_databricks_engine.py`, `test_duckdb_engine.py`.
Replace the native-driver `sys.modules` stubs with a mock (or real, for DuckDB) **Engine whose
`.connect()` yields a cursor** exposing `.description` + `.fetchall()`/`.fetchone()` returning
the same 13-col Snowflake / JSON Databricks / DESCRIBE DuckDB rows the parsers already expect.
Prefer a real in-memory DuckDB pool (per `duckdb_pool`) for DuckDB introspect; mock the ADBC
cursor for Snowflake/Databricks (no driver round-trip).

### Registry/fixture migration: `register(pool, dialect=...)` → `register(engine)`
**Source:** `conftest.py:130`, `test_pool.py:255`, `test_registry.py:34-67`,
`tests/integration/conftest.py:144-145,172-173,263-264,291-292`
**Apply to:** all of the above. Mechanical 3-arg→2-arg: build via `create_engine(config)` then
`register("name", engine)`; `get_pool(...)` assertions → `get_engine(...)` returning an Engine.

---

## No Analog Found

None. Every behavior has an in-repo analog. Two paths are **spike/blocker-gated** (not
analog-gated):

| File | Role | Data Flow | Note |
|------|------|-----------|------|
| `engines/databricks.py::introspect` (ADBC) | service | introspect | Analog = Snowflake ADBC rewrite, but UNVALIDATED — Foundry ADBC driver not installed (RESEARCH Pitfall 5 / A2). Spike-gate; fallback NotImplementedError. |
| `tests/integration/conftest.py` Databricks DDL | test fixture | — | Recording hang + missing driver (RESEARCH Open Q3). Keep native `databricks-sql` for record-mode DDL only (RESEARCH Open Q1). |

---

## Metadata

**Analog search scope:** `src/semolina/{config,registry,query,cursor,__init__}.py`,
`src/semolina/engines/{base,snowflake,duckdb,databricks}.py`, `src/semolina/cli/codegen.py`,
`tests/{conftest,unit/test_pool,unit/test_registry,unit/test_snowflake_engine}.py`,
`tests/integration/conftest.py`.
**Files scanned:** 14 (read) + grep across test suite for `register`/`get_pool`/`create_pool` call sites.
**Key carry-over enablers (already landed, branch `gsd/pytest-adbc-replay-migration`):** qmark
`?` placeholder + view-name folding (commit `799a8b0`) make the ADBC `execute()`/introspect path
viable without touching `SQLBuilder` output — do NOT change builder output (RESEARCH Pitfall 1:
cassettes match on SQL string).
**Pattern extraction date:** 2026-06-23
