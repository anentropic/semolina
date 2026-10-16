# Phase 56 summary: public surface and packaging (56-01 to 56-06)

Executed 2026-10-16 on branch `claude/phase-56`. 56-01 (the D5/D6/D7 checkpoint) is recorded
in `56-01-DECISIONS.md`; Paul chose all three, with D5 covering only Semolina-specific errors
and D7 falling back to Snowflake for an unregistered `.using()` engine. No per-plan PLAN.md
files were written: each plan was run test-first from the ROADMAP success criteria and
REQUIREMENTS, a failing-test commit followed by the fix.

## Done

| Plan | Requirement | What changed |
|---|---|---|
| 56-02 | API-01 | Builder methods take typed parameters (`metrics(*Metric)`, `dimensions(*Dimension \| Fact)`, `order_by(*Field \| OrderTerm)`, `limit(int)`, `using(str)`); the runtime checks stay. `tests/unit/test_builder_typing.py` runs basedpyright stock-strict over nine misuse lines (each must error, errors only on those lines) and a clean twin. Shared helpers moved to `tests/typecheck.py`. |
| 56-02 | API-02 | `Query` is public with `_Query` kept as an alias; `Query`, `Field`, `Engine`, `AsyncEngine`, `And`, `Or`, `Not`, `Lookup` exported from `semolina`; `engines` exports `AsyncEngine` and both engine errors; every public module has `__all__`, enforced by `test_public_surface.py`. |
| 56-03 | API-03 | `SemolinaError(Exception)` in `exceptions.py`; every Semolina error derives from it and keeps its old base (`RuntimeError`, or `ValueError` for the new `SemolinaEngineNotRegisteredError` from `get_engine`/`get_async_engine`). Engine errors moved to `exceptions.py`, re-exported from `engines.base`. `GeneratedSourceError` and `Unresolvable` joined. A source scan finds every exception class, so a new one without the base fails. `how-to/web-api.rst` gained "Catch Semolina's own errors in one place". |
| 56-04 | API-06 | typer, rich, jinja2 and griffelib are the `[cli]` extra; `[codegen-lint]` and `[all]` include it. The console script is `semolina.__main__:main`, which checks the modules and without them prints the install hint and exits 2. |
| 56-04 | API-07 | `create_engine`/`create_async_engine` resolve lazily through a PEP 562 `__getattr__`; `import semolina` imports neither the CLI's packages nor `semolina.config`. |
| 56-04 | API-08 | `semolina.testing` deleted. **Deviation:** the doctest conftest stays at `src/semolina/conftest.py` and `[tool.uv.build-backend] wheel-exclude` keeps it out of the wheel, because a top-level `src/conftest.py` collides with `tests/conftest.py` ("import file mismatch") under a plain `pytest` run. CI's packaging-smoke checks the wheel has neither, the base install has no CLI packages, and the base `semolina codegen --help` prints the hint without a traceback. |
| 56-05 | API-04 | The ABC is `SQLDialect`; `engines.sql.Dialect` and `engines.DialectABC` resolve through module `__getattr__` with a `DeprecationWarning`. `to_sql()` with no argument uses the dialect of the engine `.using()` names (sync registry, then async), else Snowflake. With no `.using()` the `default` engine is **not** consulted, per D7. |
| 56-05 | API-05 | No `adispose`/`aconnect` twins; the rule is stated in `how-to/connection-pools.rst` and `tests/unit/test_async_naming.py` enforces it. |
| 56-05 | API-09 | 93 unnecessary type/pyright ignores removed; `reportUnnecessaryTypeIgnoreComment = "error"`. |
| 56-05 | API-10 | One `threading.RLock` around register, both unregisters and reset; two tests use a store that yields between check and write, so the race is deterministic. |
| 56-06 | docs | Every page and example checked against the new API: `[cli]` install in installation, codegen, dto-codegen, warehouse-models and the CLI reference; the `to_sql()` default in queries and backends; the not-registered error in connection-pools. |

## Commits

| SHA | Subject |
|---|---|
| `685cf52` | test(query): failing basedpyright tests for builder misuse |
| `1cfc8e9` | fix(query): type the builder's parameters |
| `c67788c` | docs(planning): record D5, D6 and D7 (56-01) |
| `9ef0ae2` | docs(planning): D7 covers .using() only |
| `fdccc67` | test: failing tests for the public names and __all__ in every module |
| `7b1eb2a` | test: mark deliberate builder misuse for the type checker |
| `9d2e45a` | feat: public Query, exported builder types, __all__ in every module |
| `da31d10` | test: failing tests for a SemolinaError base (D5) |
| `3e4559f` | docs(query): resolvable refs now that Query is documented |
| `667a0d7` | feat: SemolinaError base for every Semolina error (D5) |
| `905720d` | test: failing tests for the [cli] extra and a light import semolina (D6) |
| `d5153d8` | feat!: CLI dependencies move to a [cli] extra; import semolina stays light (D6) |
| `de58dd6` | test: failing tests for SQLDialect and to_sql() following .using() (D7) |
| `86f632a` | feat: SQLDialect is the SQL-generation ABC; to_sql() follows .using() (D7) |
| `9fe1274` | test: failing concurrency tests for the registry |
| `7db5c4c` | fix(registry): lock registry mutations |
| `2cb204a` | chore: remove dead type-ignores; fail on unnecessary ones (API-09) |
| `9e3dea5` | docs: state the sync/async naming rule and guard it (API-05) |
| `4f664a0` | fix(packaging): keep the doctest conftest in the package, out of the wheel |
| `f57720a` | docs: to_sql() follows .using(); name the not-registered error (56-06) |

## 0.6-visible changes (changelog)

- `pip install semolina && semolina codegen` no longer works: the command needs
  `pip install "semolina[cli]"`. It says so and exits 2.
- The SQL-generation ABC is `SQLDialect`; the old names warn for one release.
- `to_sql()` with `.using("name")` previews in that engine's dialect, not always Snowflake.

## Gates

Full `uv run --frozen pytest -q -n auto`: 2375 passed. jaffle-shop: 13 passed.
`uvx prek run --all-files`: clean. `sphinx-build -W`: clean.
