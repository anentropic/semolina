# Pitfalls Research

**Domain:** ADBC/Arrow connection layer replacement for existing Python ORM
**Researched:** 2026-03-16
**Confidence:** MEDIUM-HIGH (ADBC is well-documented; adbc-poolhouse is unverified; Databricks ADBC path has significant gaps)

## Critical Pitfalls

### Pitfall 1: adbc-poolhouse Does Not Exist as a Published Package

**What goes wrong:**
The project plan references `adbc-poolhouse` as a core dependency for connection pooling. This package does not exist on PyPI and has no public GitHub repository. Attempting to `pip install adbc-poolhouse` will fail. Building the entire connection layer around a nonexistent library wastes the entire phase.

**Why it happens:**
The name may have been aspirational or may refer to an internal/private project. ADBC itself explicitly does not implement connection pooling -- the Apache Arrow ADBC documentation recommends using third-party pooling (e.g., SQLAlchemy QueuePool) with the `adbc_clone()` method on connections.

**How to avoid:**
Before any implementation, verify whether `adbc-poolhouse` is:
1. A private package the team will build (in which case, scope it as a deliverable, not a dependency)
2. An alias for a combination of `adbc-driver-manager` + custom pooling code
3. A misremembered name for another package

If it needs to be built, the pooling layer must be scoped as a first-phase deliverable. The ADBC PostgreSQL recipe shows a pattern using `adbc_clone()` with SQLAlchemy's QueuePool, but Snowflake and Databricks ADBC drivers may not support `adbc_clone()` identically.

**Warning signs:**
- `pip install adbc-poolhouse` fails
- No results on PyPI, GitHub, or any package registry
- Web searches return zero results for the exact name

**Phase to address:**
Phase 1 (very first task) -- resolve dependency existence before writing any code that imports it. If the package must be authored in-house, it becomes the primary deliverable of Phase 1.

---

### Pitfall 2: ADBC Snowflake Driver Does Not Support Parameterized Queries for SELECT

**What goes wrong:**
Semolina's current `build_select_with_params()` generates parameterized SQL with `%s` placeholders for Snowflake (e.g., `WHERE "country" = %s` with params `['US']`). The ADBC Snowflake driver returns `NotSupportedError: executing non-bulk ingest with bound params not yet implemented` when you attempt `cursor.execute(sql, parameters=params)` with bind parameters on a SELECT statement. The entire WHERE clause parameterization pipeline breaks.

**Why it happens:**
The ADBC Snowflake driver is a Go-based driver that only supports parameter binding for bulk ingest operations (INSERT), not for general SELECT queries. This is a fundamental limitation documented in apache/arrow-adbc issue #1144. Named parameter binding is also unsupported (issue #2193, filed September 2024, still open).

**How to avoid:**
Two approaches, ordered by preference:
1. **Inline parameters safely in SQL generation.** Since Semolina controls the predicate compilation, add a `render_inline_safe()` method that properly escapes values for SQL injection safety (not just `repr()`). This means the ADBC cursor receives fully-rendered SQL with no bind parameters.
2. **Use the DBAPI compatibility layer.** The `adbc_driver_snowflake.dbapi` module provides a PEP 249-compatible cursor that MAY support parameterized queries through a different code path. Verify this before committing to approach 1.

Either way, the existing `Dialect.placeholder` property and `build_select_with_params()` pattern must be reconsidered for the ADBC path. The `%s` / `?` placeholder system was designed for native database connectors that support bind parameters.

**Warning signs:**
- `NotSupportedError` when executing parameterized SELECT queries through ADBC
- Tests pass with MockPool but fail against real Snowflake ADBC connections
- WHERE clause filters silently ignored or erroring

**Phase to address:**
Phase 1 (connection layer foundation) -- this determines the SQL generation strategy for the entire ADBC migration. Must be resolved before MockPool can be designed, because MockPool must match the actual execution interface.

---

### Pitfall 3: Databricks Has No ADBC Driver on PyPI

**What goes wrong:**
There is no `adbc-driver-databricks` package on PyPI. The current Semolina uses `databricks-sql-connector` which is a DBAPI2 driver, not an ADBC driver. Attempting to use ADBC with Databricks requires `adbc-driver-flightsql` (the generic Arrow Flight SQL driver), but Databricks requires specific authentication (PAT tokens, OAuth) and endpoint configuration that the generic Flight SQL driver does not natively handle. The connection setup for Databricks via ADBC is fundamentally different from Snowflake.

**Why it happens:**
Databricks distributes its ADBC driver through Power BI and its own SDK channels, not as a standalone PyPI package for Python. The Databricks ADBC driver is primarily aimed at BI tools (Power BI Desktop 2.145.1105.0+), not general-purpose Python applications. The community uses `adbc-driver-flightsql` with custom configuration to connect to Databricks, but this is not well-documented and requires knowing the correct gRPC endpoint, authentication headers, and TLS configuration.

**How to avoid:**
1. **Accept asymmetric driver architecture.** Snowflake uses `adbc-driver-snowflake` (native ADBC). Databricks continues using `databricks-sql-connector` with its `fetch_arrow_all()` and `fetch_arrow_batches()` methods for Arrow-native results. The pool/cursor abstraction layer must accommodate both ADBC and non-ADBC backends.
2. **Alternatively, evaluate `adbc-driver-flightsql` for Databricks.** This requires configuring Flight SQL gRPC headers for authentication (`authorization: Bearer {token}`), setting the correct HTTP path, and handling TLS. This path is fragile and poorly documented for Databricks specifically.
3. **Design the Pool interface as backend-agnostic.** The Pool protocol should define `acquire() -> Connection` and `release(conn)` without assuming ADBC internals, allowing different backends to implement pooling differently.

**Warning signs:**
- `pip install adbc-driver-databricks` fails (package does not exist)
- Databricks connection via `adbc-driver-flightsql` requires extensive undocumented configuration
- Authentication that works with `databricks-sql-connector` does not work with Flight SQL driver
- Integration tests pass for Snowflake ADBC but fail for Databricks ADBC

**Phase to address:**
Phase 1 (architecture decision) -- the Databricks driver strategy must be decided before designing the Pool interface. This decision cascades to MockPool design, SemolinaCursor interface, and the entire abstraction layer.

---

### Pitfall 4: Arrow Type System Breaks Existing Snapshot Tests and Row Comparisons

**What goes wrong:**
Current snapshot tests store results as Python `dict` with Python-native types (`int`, `str`). ADBC returns Arrow tables where:
- INTEGER columns come back as `int64` (Arrow) which converts to Python `int` -- OK
- DECIMAL/NUMBER columns come back as `Decimal128` (Arrow) which converts to `decimal.Decimal` -- breaks `==` comparisons with `int` in snapshots
- TIMESTAMP columns come back as Arrow timestamps which convert to `datetime` or `pd.Timestamp` -- not the strings that MockEngine returns
- NULL values come back as `pyarrow.NA` or `None` depending on conversion path -- inconsistent with current `None` handling

The 12 existing snapshot entries in `test_queries.ambr` store `int` values like `'revenue': 1000`. If real ADBC returns `Decimal('1000')` or `numpy.int64(1000)`, syrupy snapshot comparison fails because `dict({'revenue': Decimal('1000')})` != `dict({'revenue': 1000})`.

**Why it happens:**
The Snowflake ADBC driver's `use_high_precision` option defaults to `True`, returning `Decimal128` for all NUMBER columns. Even with `use_high_precision=False`, zero-scale numbers return `int64` and non-zero return `float64` -- different from Python `int`/`float` in edge cases. The Arrow type system is columnar and strongly-typed; it does not auto-coerce to Python scalar types the way DBAPI `cursor.fetchall()` does.

**How to avoid:**
1. **Normalize types in SemolinaCursor.** When converting Arrow results to Row objects, explicitly cast Arrow scalars to Python native types: `int(arrow_int)`, `float(arrow_float)`, `str(arrow_string)`. Define a type coercion map in the cursor layer.
2. **Set `use_high_precision=False`** on the Snowflake ADBC driver to get `int64`/`float64` instead of `Decimal128`. This avoids Decimal drift but loses precision for high-scale numbers.
3. **Update snapshots as a conscious migration step**, not as a side effect. Run `--snapshot-update` only after the type normalization layer is verified.

**Warning signs:**
- Snapshot tests fail with type mismatches (`Decimal` vs `int`)
- `Row(revenue=Decimal('1000'))` != `Row(revenue=1000)`
- Tests pass locally (MockPool) but fail against real ADBC connections
- `isinstance(value, int)` checks fail on Arrow integer scalars

**Phase to address:**
Phase 2 (SemolinaCursor implementation) -- the cursor wrapper must include type normalization before Row construction. Snapshot migration should be a dedicated step after the cursor is verified.

---

### Pitfall 5: Breaking the Public API While Replacing Engine with Pool

**What goes wrong:**
Semolina's public API currently exports `register`, `get_engine`, `unregister`, `Result`, `Row`, and the `Engine` ABC. User code does:
```python
semolina.register("default", engine)
result = Sales.query().metrics(Sales.revenue).execute()
for row in result:
    print(row.revenue)
```

If v0.3 changes `register()` to accept a Pool instead of an Engine, or changes `.execute()` to return a cursor instead of a `Result`, all existing user code breaks. The 674 test functions and 70 doctest lines in the source code all depend on this API surface.

**Why it happens:**
The temptation to "clean break" the API for a better v0.3 design. But Semolina is already published; users (even if few) have code depending on the current interface.

**How to avoid:**
1. **Deprecate, don't delete.** Keep `register(name, engine)` working but add `register(name, pool, dialect="snowflake")` as the new preferred form. Use overloads or runtime type checking on the second argument.
2. **Keep `.execute()` returning `Result`.** The new cursor-based API (`.execute_cursor()` or similar) should be additive. The existing `.execute()` method should internally use the new pool/cursor path but continue returning `Result(rows=[Row(...), ...])`.
3. **Run the full existing test suite as a regression gate** after each phase. All 674 tests must pass unchanged (or with minimal fixture updates) throughout the migration.

**Warning signs:**
- Existing tests fail with `TypeError` or `AttributeError` on register/execute
- Doctest examples in source files break (these run as part of pytest)
- `from semolina import register, Result, Row` raises ImportError or gives wrong types

**Phase to address:**
Phase 1 (API design) -- define the compatibility contract before implementing. Create a "compatibility test" that imports and exercises every public symbol to catch regressions early.

---

### Pitfall 6: MockPool Fidelity Gap with Real ADBC Cursors

**What goes wrong:**
MockPool is designed for testing without warehouse connections. If MockPool's cursor does not faithfully replicate the ADBC cursor API surface, tests pass with MockPool but fail with real ADBC connections. Specific fidelity gaps:
- ADBC cursors have `fetch_arrow_table()`, `fetch_record_batch()`, `fetchone()`, `fetchall()`, `fetchmany()`, `description`, `rowcount`, `rownumber`, and `adbc_statement`
- ADBC `fetch_record_batch()` returns a `RecordBatchReader` that must be consumed before the cursor is closed (issue #1893) -- MockPool might not enforce this lifecycle constraint
- ADBC cursors raise specific exception types (`OperationalError`, `ProgrammingError`) -- MockPool might raise generic `Exception`

**Why it happens:**
MockPool is typically built to satisfy the immediate test requirements, not the full ADBC contract. Developers test the happy path and miss lifecycle edge cases.

**How to avoid:**
1. **Define a Cursor protocol (typing.Protocol)** that both MockCursor and real ADBC cursor wrapper must satisfy. Type-check both implementations against this protocol with basedpyright.
2. **Include lifecycle tests** in MockPool's own test suite: verify that `fetch_record_batch()` returns a reader that behaves like Arrow's `RecordBatchReader`, verify that accessing results after cursor close raises appropriately.
3. **Use the ADBC DBAPI cursor class as the reference interface**, not a custom interface. MockPool should wrap `adbc_driver_manager.dbapi.Cursor` behavior, not invent a new API.

**Warning signs:**
- Tests pass with MockPool, fail with real Snowflake pool
- MockPool cursor lacks `fetch_arrow_table()` or returns wrong type
- SemolinaCursor code has `if isinstance(cursor, MockCursor)` branches (a sign of divergent APIs)

**Phase to address:**
Phase 2 (MockPool + SemolinaCursor) -- MockPool and SemolinaCursor should be designed together against the same Protocol. Build MockPool by looking at real ADBC cursor docs, not by guessing what the API should be.

---

### Pitfall 7: Connection Lifecycle Chaos in Tests

**What goes wrong:**
Pool-based connections have fundamentally different lifecycle semantics than the current per-`execute()` connection model. Current engines create and destroy connections within each `execute()` call (context manager scope). Pools persist connections across calls. Test fixtures using `autouse=True` registry cleanup (`clean_registry` in conftest.py) do not close pool connections -- they just remove the registry entry, leaving connections open. In a test session with 674 tests, leaked connections accumulate and eventually exhaust connection limits or cause resource contention.

**Why it happens:**
The existing test infrastructure assumes stateless engines. Pools are stateful (they hold open connections). The `clean_registry` fixture resets the `_engines` dict but does not call `pool.close()` on registered pools.

**How to avoid:**
1. **Add pool cleanup to the registry `reset()` function.** When `reset()` is called, iterate registered entries and call `.close()` on any that implement a pool protocol.
2. **Use function-scoped MockPool fixtures** for unit tests (cheap to create/destroy). Only use session-scoped real pools for integration tests.
3. **Never register real pools in unit tests.** MockPool should be the only pool registered in fast test paths.
4. **Add a `Pool.close()` method** to the pool protocol and ensure teardown fixtures call it.

**Warning signs:**
- Tests hang or timeout after ~100 tests (connection exhaustion)
- "Too many connections" errors from Snowflake/Databricks in integration tests
- Tests pass individually (`pytest test_file.py`) but fail when run as full suite
- Resource warnings about unclosed connections

**Phase to address:**
Phase 2 (test infrastructure) -- update `conftest.py` fixtures before migrating any tests to pool-based execution.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Inline SQL params instead of bind params for ADBC | Works around ADBC Snowflake param limitation | Must carefully escape all value types to prevent injection; diverges from DBAPI best practice | Acceptable if ADBC bind params truly unsupported; must include thorough escaping tests |
| Keep `databricks-sql-connector` instead of ADBC for Databricks | Avoids the no-ADBC-driver problem entirely | Two different connection paradigms (ADBC for Snowflake, DBAPI for Databricks); pool abstraction must handle both | Acceptable and likely the right choice -- Databricks has no ADBC PyPI driver |
| Skip `fetch_arrow_table()` on MockPool, return static PyArrow tables | Fast MockPool implementation | Tests don't exercise real Arrow deserialization path; type coercion bugs hide until integration tests | Acceptable for unit tests; integration tests must use real Arrow path |
| Use `Any` types in Pool/Cursor protocols to avoid strict typing | Passes basedpyright immediately | Loses the strict-typing value proposition; hides type errors until runtime | Never -- basedpyright strict is a project constraint, invest in correct types |
| Global pool singleton instead of registry | Simple API (`semolina.query(...)` just works) | Cannot test multiple backends; cannot have named pools; breaks registry pattern | Never -- the registry pattern is established and valuable |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ADBC Snowflake driver | Passing connection params as keyword args like `snowflake.connector.connect()` | ADBC uses URI strings or key-value option dicts set via `AdbcDatabase(driver=..., **opts)` -- param names differ from snowflake-connector-python |
| ADBC Snowflake auth | Assuming all auth methods work (SSO, key-pair, OAuth) | ADBC Snowflake driver supports username/password and optionally JWT; some auth methods available in snowflake-connector-python are not available in the ADBC driver (experimental status) |
| ADBC Snowflake driver on Linux | Using passwords with special characters (`$6`, `*$`, `.>`) | These substrings cause authentication failures on Linux containers (issue #2543); works on macOS/Windows |
| ADBC cursor `description` | Assuming `cursor.description` format matches PEP 249 exactly | ADBC DBAPI cursor's `description` is mostly PEP 249-compatible but may have different type_code values (Arrow type IDs instead of DB-API type objects) |
| Arrow RecordBatchReader lifecycle | Closing cursor before consuming RecordBatchReader | The reader streams data from the cursor; closing the cursor invalidates the reader. Must fully consume the reader before closing (or copy data) |
| ADBC + multiple Go drivers | Loading both `adbc-driver-snowflake` and `adbc-driver-flightsql` in same process | Go runtime conflicts can cause segfaults (issue #1841); if Databricks uses FlightSQL and Snowflake uses native driver, test carefully |
| TOML config with `pydantic-settings` | Putting secrets (passwords, tokens) directly in `.semolina.toml` | TOML files are plain text, often committed to git. Use `TomlSettingsSource` for non-secret config, environment variables or vault for secrets. Support `password = "${SNOWFLAKE_PASSWORD}"` interpolation or separate credential loading. |
| TOML missing sections | Assuming `[snowflake]` section always exists in config | `pool_from_config()` must handle missing sections gracefully with clear error messages, not `KeyError` on missing TOML key |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching all results as Arrow table then converting to Row list | High memory for large result sets | Offer `fetch_record_batch_reader()` for streaming; only materialize Row list when `fetchall_rows()` is called | >100K rows, or wide tables with large string columns |
| Creating pool per query (misusing pool as connection factory) | Connection setup overhead on every query, no reuse benefit | Pool is created once and registered; queries acquire/release from pool | First query per session; real impact with >10 queries/second |
| Arrow `to_pydict()` on large tables | Copies all data from columnar to row-oriented Python dicts | Use `to_pylist()` for row-oriented access, or iterate RecordBatches for streaming | >1M rows or >1GB result sets |
| Snowflake `use_high_precision=True` (default) | All NUMBER columns return Decimal128; downstream comparisons with `int`/`float` fail or are slow | Set `use_high_precision=False` for analytics queries where Decimal precision is not needed | Always, unless user explicitly needs Decimal fidelity |
| MockPool recreated per test function | Negligible for MockPool but sets bad pattern | Use function-scoped fixtures for MockPool (cheap); session-scoped for real pools | Not a performance issue for mock; matters for integration tests |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing credentials in `.semolina.toml` committed to git | Credential exposure in repository history | Support env var references in TOML (`password = "$SNOWFLAKE_PASSWORD"`); document that secrets must come from environment, not TOML; add `.semolina.toml` to `.gitignore` template |
| Inlining SQL params without proper escaping | SQL injection if user-controlled values reach predicates | Even though Semolina controls predicate compilation, the escape function must handle all SQL types (strings with quotes, NULLs, arrays); add injection test suite |
| Connection string logged in error messages | Credentials visible in logs, tracebacks, error reports | Redact connection params in exception messages; only include non-sensitive params (account, database) in error strings |
| Pool connection reuse across tenants | If Semolina is used in multi-tenant app, pooled connections may carry session state (SET ROLE, USE SCHEMA) from previous queries | Document that pools are per-tenant; provide `pool.reset_session()` hook or create separate pools per tenant |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Breaking `.execute()` return type from `Result` to cursor | All existing user code (`for row in result`) breaks | Add `.execute_cursor()` as new method; keep `.execute()` returning `Result` |
| Requiring Arrow knowledge to use basic queries | Users who just want `row.revenue` must understand PyArrow tables | SemolinaCursor convenience methods (`fetchall_rows()`) should return `list[Row]` like today; Arrow methods are opt-in for power users |
| Changing `register("name", engine)` signature | Existing setup code breaks | Accept both `Engine` and `Pool` via overload/union type; deprecation warning for Engine form |
| TOML config errors with unhelpful messages | "KeyError: 'snowflake'" when section missing | Validate TOML structure early with clear messages: "Missing [snowflake] section in .semolina.toml. See docs for config format." |
| Silent type coercion in Arrow -> Row conversion | `row.revenue` is `Decimal('1000')` instead of `int(1000)` -- breaks downstream math, comparisons, JSON serialization | Normalize Arrow scalars to Python native types in cursor layer; document the type mapping |
| MockPool cannot load fixture data | Users familiar with `MockEngine.load("view", data)` find no equivalent | MockPool must provide `load()` or equivalent fixture injection; make migration path obvious |

## "Looks Done But Isn't" Checklist

- [ ] **Pool registration:** Registering a pool works, but does `get_engine()` still work for backward compatibility? Does it return something that old code can call `.execute(query)` on?
- [ ] **SemolinaCursor:** Has `fetchall_rows()`, but does it also implement `__iter__` for `for row in cursor` patterns? Does `fetchone_row()` return `None` when exhausted (PEP 249 convention)?
- [ ] **MockPool:** Returns fixture data, but does `MockPool.acquire()` return a connection with a `.cursor()` method? Does the mock cursor implement `fetch_arrow_table()` returning a real `pyarrow.Table`?
- [ ] **TOML config:** Loads `[snowflake]` section, but what about `[default]` pool name mapping? What if user has both `[snowflake]` and `[databricks]` sections -- does it register both pools?
- [ ] **Type normalization:** Integer columns normalize correctly, but what about `BOOLEAN` (Arrow `bool_()` vs Python `bool`)? `DATE` (Arrow `date32` vs `datetime.date`)? `ARRAY` types? `VARIANT`/`OBJECT` (Snowflake JSON)?
- [ ] **Error messages:** Pool connection failures show helpful message, but do they include which pool name failed and what dialect was expected?
- [ ] **Docstrings and doctests:** All new public methods have docstrings, but do the doctests actually run? Are they registered in pytest's doctest collection (testpaths includes `src`)?
- [ ] **`__init__.py` exports:** New public symbols (Pool, SemolinaCursor, MockPool, Dialect enum) are importable from `semolina`, but are they in `__all__`?
- [ ] **Snapshot tests:** Updated to pass, but were they verified against real warehouse data, or just regenerated from MockPool? MockPool snapshots may mask type/ordering differences.
- [ ] **`query()` shorthand:** `Sales.query(metrics=..., dimensions=...)` works, but does it compose with `.where()`, `.order_by()`, `.limit()`? Does it reject invalid combinations (metrics + random keyword)?

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| adbc-poolhouse doesn't exist | MEDIUM | Build minimal pool abstraction in-house (~200 lines); use ADBC `adbc_clone()` or simple create/close pattern; scope as Phase 1 deliverable |
| ADBC bind params not supported | LOW | Switch to inline SQL rendering with proper escaping; update `build_select_with_params()` to have an `inline_mode` flag; add SQL injection test suite |
| No Databricks ADBC driver | LOW | Keep `databricks-sql-connector` as Databricks backend; design Pool interface to accommodate non-ADBC backends; Databricks connector already has `fetch_arrow_all()` for Arrow results |
| Arrow types break snapshots | LOW | Add type normalization in SemolinaCursor; regenerate snapshots after normalization is verified; existing snapshot format (Python dicts) is fine -- just normalize values |
| Public API broken | HIGH | If caught early (by running existing tests): fix API compatibility layer. If shipped to users: semver major bump required, migration guide needed |
| MockPool fidelity gap | MEDIUM | Define Protocol, type-check both Mock and real implementations; add integration smoke test that verifies MockPool and real pool produce same Row output for same query |
| Connection leak in tests | LOW | Add `pool.close()` to fixture teardown; update `registry.reset()` to close pools; typically caught quickly by CI timeout or connection limit errors |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| adbc-poolhouse doesn't exist | Phase 1 (first task) | `pip install` succeeds, or in-house pool module exists and passes import |
| ADBC bind params unsupported | Phase 1 (SQL generation) | Parameterized WHERE queries execute successfully against Snowflake ADBC with no `NotSupportedError` |
| No Databricks ADBC driver | Phase 1 (architecture decision) | Databricks connection strategy documented and verified (either Flight SQL or keep databricks-sql-connector) |
| Arrow types break snapshots | Phase 2 (SemolinaCursor) | `row.revenue` returns Python `int` not `Decimal` or Arrow scalar; snapshot tests pass without type hacks |
| Public API broken | Phase 1 (API design) | All 674 existing tests pass with zero code changes; `from semolina import register, Result, Row` works unchanged |
| MockPool fidelity gap | Phase 2 (MockPool) | Cursor Protocol satisfied by both MockCursor and real ADBC cursor wrapper; `basedpyright` passes on both |
| Connection leak in tests | Phase 2 (test infra) | Full test suite runs without connection exhaustion; `registry.reset()` closes pools |
| TOML config edge cases | Phase 3 (config) | Missing sections, empty values, invalid types all produce clear error messages, not `KeyError` |
| Snowflake Linux auth issue | Phase 4 (CI) | CI pipeline on Linux passes with Snowflake ADBC connection; passwords without special chars selected for CI credentials |

## Sources

- [ADBC Snowflake driver parameterized query limitation (issue #1144)](https://github.com/apache/arrow-adbc/issues/1144)
- [ADBC Snowflake named parameter binding (issue #2193)](https://github.com/apache/arrow-adbc/issues/2193)
- [ADBC Snowflake Linux auth failures with special chars (issue #2543)](https://github.com/apache/arrow-adbc/issues/2543)
- [ADBC Snowflake + FlightSQL segfault when both loaded (issue #1841)](https://github.com/apache/arrow-adbc/issues/1841)
- [ADBC cursor RecordBatchReader lifecycle (issue #1893)](https://github.com/apache/arrow-adbc/issues/1893)
- [ADBC Snowflake memory allocation errors (issue #1283)](https://github.com/apache/arrow-adbc/issues/1283)
- [ADBC Snowflake driver documentation - type mappings](https://arrow.apache.org/adbc/current/driver/snowflake.html)
- [ADBC Python DBAPI cursor API](https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html)
- [adbc-driver-snowflake on PyPI](https://pypi.org/project/adbc-driver-snowflake/)
- [adbc-driver-flightsql on PyPI](https://pypi.org/project/adbc-driver-flightsql/)
- [Apache Arrow ADBC connection pooling recipe (PostgreSQL)](https://github.com/apache/arrow-adbc/blob/main/docs/source/python/recipe/postgresql_pool.py)
- [ADBC format specification](https://arrow.apache.org/docs/format/ADBC.html)
- [Databricks ADBC driver for Power BI](https://docs.databricks.com/aws/en/partners/bi/power-bi-adbc)
- [Apache Arrow ADBC 22 release notes (January 2026)](https://arrow.apache.org/blog/2026/01/09/adbc-22-release/)
- [PyArrow data types and type system](https://arrow.apache.org/docs/python/data.html)
- [Snowflake ADBC quick start guide](https://medium.com/snowflake/a-quick-start-guide-to-the-snowflake-adbc-driver-with-python-6de3eb28ee52)
- [ADBC Arrow Driver for Databricks (community post)](https://dataengineeringcentral.substack.com/p/adbc-arrow-driver-for-databricks)

---
*Pitfalls research for: ADBC/Arrow connection layer replacement in Semolina ORM v0.3*
*Researched: 2026-03-16*
