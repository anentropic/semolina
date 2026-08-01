# Phase 46: Async Query Surface - Research

**Researched:** 2026-08-01
**Domain:** Thread-offloaded async DB access over ADBC; loop-agnostic (asyncio + Trio) library design; Python optional-extra packaging
**Confidence:** HIGH (the entire upstream async surface was read from the actual wheel source; the lint gate was executed; the replay path was read from the installed plugin)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Engine architecture

- **D-01:** `create_async_engine()` is a **separate constructor** returning a distinct
  `AsyncEngine` type owning exactly one poolhouse `AsyncPool`. This mirrors
  SQLAlchemy, which was checked against the official docs: `create_async_engine()` is a
  distinct function returning `AsyncEngine`, and `AsyncAdaptedQueuePool` "is used by
  default when using `AsyncEngine` engines that were generated from
  `create_async_engine()`". One pool per engine, mode fixed at construction.
- **D-02:** `AsyncEngine` is a **sibling** of `Engine`, not a proxy wrapping one.
  SQLAlchemy's `AsyncEngine`-wraps-`.sync_engine` arrangement works only because its
  async is real async I/O bridged by greenlet over a shared pool. Semolina's async is
  thread-offload and poolhouse's `AsyncPool` is a genuinely separate object from the
  sync `QueuePool`, so there is nothing to proxy. Rejected explicitly.
- **D-03:** One `Engine` holding two pools was **rejected** — no precedent in
  SQLAlchemy, doubles the warehouse connection budget, and breaks the v0.6
  "an Engine owns exactly one pool" invariant.
- **D-04:** `AsyncEngine` shares the dialect and SQL builder with `Engine` unchanged.
  `build_select_with_params()` output is identical for both paths; only connection
  checkout differs (~12 lines). Do not duplicate SQL generation.

#### Registry

- **D-05:** **Separate registries** for sync and async engines, chosen for cleaner
  typing over a single registry holding a union of engine kinds. This avoids
  `.using("default").aexecute()` failing at runtime because the registered engine was
  the sync kind. Planner decides the exact public surface (e.g. an async-specific
  `register`/`get_engine` pair vs. a namespaced variant).

#### Cursor

- **D-06:** **Separate cursor types** — an async cursor distinct from `SemolinaCursor`,
  consistent with the engine split. Avoids a single class where calling a wrong-mode
  method silently returns a coroutine.
- **D-07:** The async cursor mirrors the existing batch-buffer state machine in
  `cursor.py:238-285` (`_batch_rows` / `_batch_pos` / `_stream_exhausted`), awaiting
  `AsyncRecordBatchReader.__anext__` instead of calling `reader.read_next_batch()`.
  Buffering logic is duplicated rather than shared — a sync and async iterator cannot
  cleanly share a body.

#### Connection lifetime (highest-risk area)

- **D-08:** The async path uses **manual checkout with an explicit guard**, matching the
  sync `Engine.execute()` discipline at `engines/base.py:173-186` — check out, keep the
  connection alive past the call, hand it to the cursor, close it in the cursor's close,
  and catch `BaseException` to return the slot on the error path.
- **D-09:** Do **not** follow the `async with await pool.connect() as conn: ... return
  cursor` sketch in the source todo. It returns the connection to the pool while the
  reader is still live, which contradicts the existing `fetch_record_batch` constraint
  that "the cursor must outlive the reader" (arrow-adbc #1893, noted at
  `cursor.py:179-180`).
- **D-10:** The cursor close path must tolerate an **already-invalidated connection**.
  On cancellation poolhouse passes `on_abort=self._owner.invalidate` for poison
  recovery, so the connection may be dead before Semolina closes it. The sync path never
  faced this.

#### Dependencies and packaging

- **D-11:** A `semolina[async]` extra pins `adbc-poolhouse[async]>=1.5.0`. A plain
  `pip install semolina` gains no new dependency. The base pin is currently
  `adbc-poolhouse>=1.3.1` (pyproject.toml:11) and **1.3.1 is what is installed** —
  verified, it has no async surface at all. The floor bump is real work, and nothing
  else in this phase can be written or tested until it lands. Sequence it first.
- **D-12:** The async engine must construct its pool via the **config / `dbapi_module`
  path**, not `create_async_pool(driver_path=...)`. The native-shared-library form
  bypasses the Python dbapi module entirely, which would defeat cassette interception
  (see D-15).

#### Enforcing Posture A (ASYNC-05)

- **D-13:** Enforce via ruff's `flake8-tidy-imports` banned-API (`TID251`) scoped to
  `src/semolina/`, banning `asyncio` and `anyio` imports, rather than a bespoke grep
  script. Ruff already runs in the quality gate; `TID` is not currently in
  `[tool.ruff.lint] select` (`E,F,W,I,UP,B,SIM,TCH,D`), so this adds a rule.
- **D-14:** The ban scopes to `src/semolina/` **only**. Tests may import anyio freely —
  the Trio half of the test matrix requires it.

#### Testing

- **D-15:** Cassette replay through the async path is **viable unmodified** —
  established by reading the poolhouse 1.5.0 source (see Canonical References). This was
  a user-set gate: if replay could not intercept `AsyncCursor`, work stops and
  pytest-adbc-replay gets updated first. It can, so the phase proceeds.
- **D-16:** **Task 1 is a spike** proving one existing cassette replays end-to-end
  through the async path. D-15 is a structural inference from source reading, not an
  executed test — poolhouse 1.5.0 is not installed in the project venv. Nothing else
  should be built on the assumption until the spike confirms it.
- **D-17:** The async test matrix runs under **both asyncio and Trio** via the anyio
  pytest plugin.

#### Sequencing

- **D-18:** **TOOL-01 lands last**, as the phase's final commit. Flipping
  `git.branching_strategy` back to `"milestone"` re-arms the GSD commit helper's branch
  auto-switching — the exact behaviour that stranded commits during Phase 44 and caused
  it to be set to `"none"`. Doing it early would migrate this phase's own task commits
  mid-flight.

### Claude's Discretion

- Exact public naming and shape of the async registry surface (D-05).
- Exact name of the async cursor type (D-06).
- Whether `aexecute()` returns an awaited-open cursor (`async with await
  engine.aexecute(q) as cur:`) or an async context manager (`async with
  engine.aexecute(q) as cur:`). ASYNC-01's wording ("`await engine.aexecute(query)`")
  leans to the former; planner may choose on ergonomics.
- Whether an async `fetch_arrow_table()` twin is pulled forward. Not required by
  ASYNC-01..06, but Phase 49 needs it and it sits ~3 lines from the streaming work.
- How `ConnectionBusyError` is surfaced (D-20 below) — message and whether it is
  wrapped in a Semolina exception type.

### Deferred Ideas (OUT OF SCOPE)

- **Posture B concurrency sugar** — fan-out/timeout helpers Semolina orchestrates, which
  would require taking an anyio dependency. Tracked as ASYNC-F1 in REQUIREMENTS.md.
- **Async introspection / codegen** using poolhouse's async `adbc_get_objects` /
  `adbc_get_table_schema`. Tracked as ASYNC-F2.
- **Async `fetch_df()` / `fetch_polars()`** — RESULT-01, Phase 49.
- **Async `.into(DTO)` per-batch conversion** — DTO-02, Phase 49, which hard-depends on
  the cursor this phase delivers.
- **Partitioned reads** (`adbc_execute_partitions`) for intra-query parallelism —
  driver-dependent, listed Out of Scope in REQUIREMENTS.md.
- **FastAPI integration package** (lifespan helper, `Depends()` engine provider, response
  serialization) — gated on this surface existing; its own milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ASYNC-01 | `await engine.aexecute(query)`, same result surface as `.execute()` | Skeleton in Code Examples §1; `AsyncPool.connect` / `AsyncConnection.cursor` / `AsyncCursor.execute` signatures all verified from the wheel. Note the "same surface" caveat in Open Question 1 |
| ASYNC-02 | `await Sales.query()...aexecute()` | `_Query.execute()` at `query.py:386-419` is a 4-line body; `aexecute()` is a near-copy against the async registry (Code Examples §3) |
| ASYNC-03 | `async for row in result`, batches off-thread, mapped to `Row` | `AsyncRecordBatchReader.__aiter__`/`__anext__` verified; per-pull offload confirmed; Semolina mirrors `cursor.py:238-285` (Code Examples §2). **Close-ordering constraint in Pitfall 1 is mandatory** |
| ASYNC-04 | `semolina[async]` extra pins `adbc-poolhouse[async]>=1.5.0`; default install unchanged | Packaging section. **Floor must be `>=1.6.0`, not `>=1.5.0` — see Finding 1**; import must stay lazy — see Pitfall 3; CI smoke-job pattern already exists at `ci.yml:149-169` |
| ASYNC-05 | Zero `asyncio.*` / no anyio import in library code, automated check, green under asyncio + Trio | TID251 config **executed and verified** on both ruff versions in play (Code Examples §5). Trio precondition verified: `anyio.to_thread.run_sync` is poolhouse's sole chokepoint. `trio` is a **separate dependency** — see Finding 6 |
| ASYNC-06 | Cancellation reaches the warehouse via `adbc_cancel` | Fully delivered upstream by `cancellable_offload`; Semolina writes **zero** cancellation code but must not break await transparency — see Don't Hand-Roll and Pitfall 2. **Not testable through cassettes** — see Finding 10 |
| TOOL-01 | `git.branching_strategy` restored to `milestone` | `.planning/config.json` currently reads `"branching_strategy": "none"`; single-key edit, sequenced last per D-18 |
</phase_requirements>

## Summary

The hard part of this phase is already built, upstream, and correct. `adbc-poolhouse`
ships a complete async stack behind an `[async]` extra: `create_async_pool` →
`AsyncPool` → `AsyncConnection` → `AsyncCursor` → `AsyncRecordBatchReader`, with every
blocking ADBC call funnelled through one `anyio.to_thread.run_sync` chokepoint, a
per-pool `CapacityLimiter` sized to `pool_size + max_overflow`, shielded teardown, and a
two-task watcher/worker structure that fires the driver's `adbc_cancel` when the
surrounding scope is cancelled. I read all eight modules of that subpackage from the
1.6.1 wheel. Semolina's job is genuinely thin: a sibling `AsyncEngine`, a sibling async
cursor that mirrors the existing batch-buffer state machine, an async registry, an
`aexecute()` on `_Query`, a packaging extra, and a lint rule. No cancellation code, no
thread-pool code, no anyio import.

Three findings change the plan's shape rather than just informing it. First, **the
version floor in ASYNC-04 is wrong**: `create_async_pool` in 1.5.0/1.5.1 hard-codes
`pool_size=5` and ignores the config's own `pool_size`; the `_resolve_tuning` helper that
fixes this landed in 1.6.0. Pinning `>=1.5.0` would silently give an in-memory DuckDB
async engine five isolated databases. Second, **close ordering is mandatory and
non-obvious**: poolhouse holds a `_reader_open` lifetime lock on the connection for a
live reader's whole life, and both `AsyncCursor.close()` and `AsyncConnection.close()`
take the foreign tier of that guard — so calling either before closing the reader raises
`ConnectionBusyError`. Third, **cassette replay works and needs no recording**: the
plugin's patch point is `driver_mod.connect`, upstream of the entire async stack, and
`@pytest.mark.adbc_cassette("<name>")` overrides node-id-derived cassette paths, so an
existing cassette directory can simply be copied to a named path — which also stops the
asyncio/Trio parametrization from doubling the cassette tree.

The highest-risk area is exactly where CONTEXT.md predicted: connection lifetime. But
the risk is now concrete rather than vague. Poolhouse's `__aexit__` deliberately bypasses
the `_in_use` guard while explicit `close()` does not; `invalidate()` clears
`_reader_open` and makes a later `close()` a documented safe no-op; and a leaked async
cursor leaks a pool connection permanently, because no `__del__` can await. That last
point is a real regression against the sync path's `__del__` safety net and must be
documented, not papered over.

**Primary recommendation:** Bump the floor to `adbc-poolhouse[async]>=1.6.1`, then build
`AsyncEngine` + `AsyncSemolinaCursor` as siblings whose close path is strictly
`reader → cursor → connection`, each step tolerant of an already-invalidated connection;
test on file-backed DuckDB for concurrency, real DuckDB for cancellation, and copied
named cassettes for the warehouse dialects.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Event-loop non-blocking (thread offload) | adbc-poolhouse `_async/_offload.py` | — | Single `anyio.to_thread.run_sync` chokepoint upstream; the concurrency envelope (`pool_size + max_overflow`) lives with the pool, so the executor must too |
| Loop-backend agnosticism (asyncio/Trio) | adbc-poolhouse (anyio) | Semolina (neutral awaits) | Semolina achieves it by *not* importing a loop library; agnosticism is inherited, not implemented |
| Query cancellation → `adbc_cancel` | adbc-poolhouse `_async/_cancel.py` | Semolina (transparency only) | Requires a second task watching an Event while the worker blocks; Semolina cannot do this without anyio, and does not need to |
| Connection checkout / check-in | adbc-poolhouse `AsyncPool` / `AsyncConnection` | Semolina (lifetime orchestration) | Pool owns the slot; Semolina decides *when* to release it because the reader must outlive nothing but the cursor |
| Poison recovery on cancel (`invalidate`) | adbc-poolhouse | Semolina (tolerate it) | Driven from inside `cancellable_offload`; Semolina's only duty is a close path that survives it |
| SQL generation | Semolina `engines/sql.py` | — | Dialect-specific, shared byte-identically between sync and async (D-04) |
| Arrow batch → `Row` mapping | Semolina async cursor | — | The ORM ergonomics layer; a pure CPU map, correctly left on the loop thread |
| Engine construction / config resolution | Semolina `config.py` | adbc-poolhouse `create_async_pool` | Semolina owns TOML/config→dialect resolution; poolhouse owns pool building |
| Named engine lookup | Semolina `registry.py` | — | Purely a Semolina concept; no poolhouse equivalent |
| Posture A enforcement | ruff (`TID251`) | CI | A static property of the source tree, so a linter is the right enforcer |
| DuckDB `semantic_views` extension load | Semolina `config.py` via SQLAlchemy `connect` event | adbc-poolhouse inner `QueuePool` | Semolina-specific extension; **must attach to the inner sync pool** — see Finding 4 |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `adbc-poolhouse[async]` | **>=1.6.1** (latest 1.6.1) | The entire async ADBC stack: `create_async_pool`, `AsyncPool`, `AsyncConnection`, `AsyncCursor`, `AsyncRecordBatchReader`, `close_async_pool` | Already the project's pool layer (base pin `adbc-poolhouse>=1.3.1` at `pyproject.toml:11`); same author; the async surface was purpose-built for this consumer. `[async]` declares `anyio>=4.13` [VERIFIED: PyPI JSON `requires_dist`, `anyio>=4.13; extra == "async"`] |
| `anyio` | >=4.13 (latest 4.14.2) | Transitive only — poolhouse's offload + cancellation primitives. **Semolina never imports it** | Pulled by `adbc-poolhouse[async]`; already present in the venv at 4.13.0 [VERIFIED: `uv.lock:121-130`, `anyio-4.13.0` in `.venv/lib/python3.14/site-packages/`] |

### Supporting (dev/test only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `trio` | >=0.33.0 | The second half of the D-17 loop matrix | **Required explicitly** — `anyio>=4.13` does not install trio (Finding 6). Add to `[dependency-groups] dev` (or use `anyio[trio]`). Supports 3.11 and 3.14, both CI matrix versions [VERIFIED: PyPI JSON — `requires_python: ">=3.10"`, classifiers include `Programming Language :: Python :: 3.14`] |
| `anyio` pytest plugin | ships with anyio | `pytest.mark.anyio` + parametrized `anyio_backend` fixture | Auto-registered via the `pytest11` entry point — no config needed [VERIFIED: `anyio-4.13.0.dist-info/entry_points.txt` contains exactly `[pytest11]\nanyio = anyio.pytest_plugin`] |
| `pytest-adbc-replay` | >=1.1.1 (current, latest is 1.1.1) | Cassette replay for Snowflake/Databricks async tests | **No update needed** — verified sync-only and async-transparent (Finding 9) |
| `ruff` | >=0.15.1 dev / v0.9.6 pre-commit hook | TID251 Posture A gate | Config verified working on **both** versions (Code Examples §5) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `adbc-poolhouse[async]>=1.6.1` | `>=1.5.0` as ASYNC-04 literally specifies | Rejected: 1.5.x ignores `config.pool_size` in `create_async_pool` (Finding 1). Silent misconfiguration, not a missing feature |
| Deferred import of `create_async_pool` | PEP 562 `__getattr__` in `semolina/__init__.py` | Both work. PEP 562 mirrors poolhouse's own approach and gives a clean `AttributeError`/`ImportError` boundary; deferred function-body import matches the existing in-repo precedent at `engines/base.py:130-136` and is fewer moving parts. **Recommend the deferred import** |
| `trio` in the dev group | `anyio[trio]` | Equivalent. `anyio[trio]` self-documents the intent; a bare `trio` pin is more explicit about the version floor. Either is fine |
| TID251 lint gate | A bespoke `grep -r 'asyncio\.'` script | Rejected per D-13, and independently correct: grep false-positives on docstrings that *discuss* asyncio (this phase will write several). TID251 is semantic. Caveat in Pitfall 6 |

**Installation:**

```bash
# The floor bump (sequence first, per D-11)
uv add 'adbc-poolhouse>=1.6.1'
uv add --optional async 'adbc-poolhouse[async]>=1.6.1'
uv add --dev 'trio>=0.33.0'
```

**Version verification** (run this session):

```
$ curl -s https://pypi.org/pypi/adbc-poolhouse/json | ... -> latest: 1.6.1
  releases: 1.0.0 1.0.1 1.2.0 1.3.0 1.3.1 1.4.0 1.5.0 1.5.1 1.6.0 1.6.1
  provides_extra: [all, async, bigquery, databricks-python, databricks-python-m2m,
                   duckdb, flightsql, postgresql, quack, snowflake, sqlite]
  anyio>=4.13; extra == "async"
$ trio -> 0.33.0    anyio -> 4.14.2 (installed 4.13.0)    pytest-adbc-replay -> 1.1.1
```

[VERIFIED: pypi.org/pypi/{adbc-poolhouse,trio,anyio,pytest-adbc-replay}/json, fetched 2026-08-01]

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `adbc-poolhouse` | PyPI | 10 releases, 1.0.0 → 1.6.1 | n/a (seam returned no signal) | `github.com/anentropic/adbc-poolhouse` | OK | Approved — already a project dependency (`pyproject.toml:11`), authored by this project's own author, wheel source read directly this session |
| `anyio` | PyPI | 70 releases since 1.0.0 | n/a (seam returned no signal) | (no `Source` project_url; upstream is `agronholm/anyio`) | OK | Approved — transitive only, declared by `adbc-poolhouse[async]` itself, already installed at 4.13.0 |
| `trio` | PyPI | 43 releases since 0.0.0 | n/a (seam returned no signal) | `github.com/python-trio/trio` | OK | Approved — dev/test only |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none on the merits.

*Provenance note, stated plainly:* `gsd-tools query package-legitimacy check --ecosystem
pypi` returned `SUS` for all three with reasons `unknown-age`, `unknown-downloads`,
`no-repository` and every signal field `null` — i.e. the seam has no PyPI signal source
wired up, so the verdicts carry no information about these packages. I therefore verified
each independently against the PyPI JSON API (release history and repository URL, quoted
above) and, for `adbc-poolhouse`, by downloading and reading the wheel. No package here
was discovered via WebSearch or training recall: `adbc-poolhouse` is an existing project
dependency, `anyio` is declared by poolhouse's own `[async]` extra metadata, and `trio`
is the canonical name of the alternate loop that ASYNC-05 names explicitly. No
`checkpoint:human-verify` gate is warranted.

## Architecture Patterns

### System Architecture Diagram

```
               +---------------------------------------------+
       +-------+ async def handler  (asyncio or Trio)        |
       |       +----------------------+----------------------+
cancel |                              |
       |                              v
       |       +----------------------+----------------------+
       |       | Semolina: _Query.aexecute / AsyncEngine     +<----+ batches
       |       +----------------------+----------------------+     |
       |                              |                            |
       |                              v                            |
       |       +----------------------+----------------------+     |
       |       | poolhouse: AsyncPool / AsyncCursor / reader |     |
       |       +----------------------+----------------------+     |
       |                              |                            |
       |                              v                            |
       |       +----------------------+----------------------+     |
       |       | anyio offload -> worker thread              |     |
       |       +----------------------+----------------------+     |
       |                              |                            |
       |                              v                            |
       |       +----------------------+----------------------+     |
       +------>+ ADBC C call, GIL released -> warehouse      +-----+
               +---------------------------------------------+
```

Reading the diagram: the handler enters at the top. Only **one** box belongs to Semolina,
and everything below it is poolhouse/anyio — that boundary *is* Posture A. The `cancel`
riser on the left shows framework cancellation travelling past Semolina entirely: it is
received by poolhouse's watcher task, which fires `cursor.adbc_cancel()` at the in-flight
C call. The `batches` riser on the right shows the result path stopping at Semolina, which
maps each `pyarrow.RecordBatch` to `Row` objects on the loop thread — poolhouse fetches
off-thread, Semolina maps.

### Recommended Project Structure

```
src/semolina/
├── config.py              # + create_async_engine()  (sibling of create_engine, sync def)
├── registry.py            # + separate _async_engines dict + async lookup surface (D-05)
├── cursor.py              # unchanged
├── acursor.py             # NEW: AsyncSemolinaCursor (mirrors cursor.py:238-285)
├── query.py               # + _Query.aexecute()  (near-copy of execute(), query.py:386-419)
├── engines/
│   ├── base.py            # unchanged
│   └── abase.py           # NEW: AsyncEngine (sibling of Engine, per D-02)
└── __init__.py            # + lazy/deferred exports of the async surface
```

Placing `AsyncEngine` in a *new* module rather than in `engines/base.py` keeps
`import semolina.engines.base` free of any async-adjacent import, which matters for the
Pitfall 3 packaging constraint. Backend subclasses are **not** needed: `introspect()` is
the only abstract method on `Engine` and async introspection is explicitly deferred
(ASYNC-F2), so `AsyncEngine` can be concrete and backend-agnostic — it needs only the
pool and the dialect.

### Pattern 1: Sibling constructor, synchronous

`create_async_pool` is a plain `def`, not a coroutine — pool construction does no I/O.

> "Pool construction stays synchronous --- `_create_pool_impl` does no per-call I/O,
> so `create_async_pool` need not be a coroutine. Only `connect` / `close` (and the
> per-call cursor methods in Plan 03) are offloaded to worker threads."
> [VERIFIED: adbc-poolhouse 1.6.1 wheel, `_async/_factory.py:12-15` module docstring]

So `create_async_engine()` is a plain `def` too — structurally identical to
`config.py:178-238`, differing only in `create_pool` → `create_async_pool` and the
DuckDB listener target (Finding 4). This also matches SQLAlchemy, where
`create_async_engine()` is synchronous. Teardown is the asymmetric half:
`close_async_pool` **is** a coroutine, so `AsyncEngine.dispose()` must be `async def`.

### Pattern 2: The mandatory close order

```
reader.close()   ->   cursor.close()   ->   connection.close()
```

This is not a style preference; the middle two raise if the first is skipped. See
Pitfall 1 for the verbatim source basis.

### Pattern 3: Transparent awaits (Posture A)

A bare `async def` whose body only `await`s poolhouse coroutines is loop-agnostic *and*
cancellation-transparent by construction. The corollary is a prohibition: any
`except Exception` that swallows, any retry loop, any shielding in Semolina's async path
would break ASYNC-06 silently. Catch `BaseException` only to release a resource and
**always re-raise**, exactly as the sync path does at `engines/base.py:177-184`.

### Anti-Patterns to Avoid

- **Wrapping the sync `Engine.execute` in a thread yourself.** The offload must happen
  inside poolhouse so the worker count matches the pool's `CapacityLimiter`. Offloading
  in Semolina would need Semolina to read poolhouse's pool sizing to size its executor.
- **`AsyncEngine` proxying a sync `Engine`.** Rejected in D-02, and confirmed by the
  source: `AsyncPool` wraps a `QueuePool` it builds itself; there is no shared pool to
  proxy.
- **`async with await pool.connect() as conn: ... return cursor`.** The source todo's
  sketch. Rejected in D-09 and independently wrong for a second reason: `__aexit__`
  checks the connection in, which closes the fairy and fires the pool's reset event,
  after which reading the still-open reader surfaces `pyarrow.lib.ArrowInvalid`.
- **Sharing one `AsyncEngine`'s connection across tasks.** Guarded upstream with
  `ConnectionBusyError`; the fix is always "check out another connection", which
  `aexecute()` does per call anyway.
- **A `__del__` that tries to clean up the async cursor.** Cannot await; and poolhouse's
  own reader `__del__` deliberately only warns for exactly this reason.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Running blocking ADBC off the loop | `anyio.to_thread.run_sync` / `run_in_executor` wrappers | `AsyncCursor.*` (offloads internally) | Executor must be sized to `pool_size + max_overflow`; that number lives in poolhouse |
| Bounding async concurrency | A semaphore around `aexecute` | poolhouse's per-pool `anyio.CapacityLimiter(pool_size + max_overflow)` | Already exact, and deliberately not anyio's global 40-token default |
| Cancelling an in-flight query | A timeout wrapper + `cursor.adbc_cancel()` | `cancellable_offload` (automatic) | Needs a watcher task parked on an Event *while* the worker blocks, a shield so the abort can't be aborted, an `aborted_by_us` flag so the driver's interrupt isn't mistaken for a real error, and `ExceptionGroup` unwrapping. ~90 lines of subtle upstream code |
| Recovering a poisoned connection after cancel | Manual `invalidate()` bookkeeping | `on_abort=self._owner.invalidate`, wired by poolhouse | Runs off a **dedicated 1-token limiter** to avoid deadlocking behind the worker it just aborted |
| End-of-stream signalling across the thread boundary | Letting `StopIteration` propagate from the worker | poolhouse's `_EXHAUSTED` sentinel → `StopAsyncIteration` | A bare `StopIteration` crossing `to_thread.run_sync` becomes `RuntimeError` under both asyncio and Trio |
| Loop detection (asyncio vs Trio) | `sniffio` / `asyncio.get_running_loop()` | Nothing — neutral awaits | Importing either would itself violate ASYNC-05 |
| Async iteration over Arrow | A custom async wrapper over `RecordBatchReader` | `AsyncRecordBatchReader` | Wraps by composition against a `_SyncReader` protocol, so no concrete Arrow class leaks — and that protocol is why replay cursors work |
| Detecting concurrent connection misuse | Locks in Semolina | `ConnectionBusyError` | Deliberately rejects rather than serializes, so the bug surfaces |

**Key insight:** In this domain the correct amount of Semolina async code is *startlingly
small*, and every instinct to add more (a timeout helper, a gather helper, a retry) either
duplicates poolhouse or breaks ASYNC-05. The phase succeeds by writing plumbing and
resisting scope.

## Common Pitfalls

### Pitfall 1: `ConnectionBusyError` on close, because a reader is still open

**What goes wrong:** `await cursor.close()` or `await conn.close()` raises
`ConnectionBusyError` even though nothing is running concurrently.

**Why it happens:** A live reader locks its connection for its whole lifetime, and the
lock is only cleared by `reader.close()` — never by draining it.

> "`_reader_open`: True for the WHOLE lifetime of a live Arrow reader on this
> connection (Model B, D-29-08/09), distinct from the per-call `_in_use`. ... Set by
> `fetch_record_batch` and cleared by `reader.close()` / checkin (plan 03);
> `_exit_offload` NEVER touches it."
> [VERIFIED: adbc-poolhouse 1.6.1 wheel, `_async/_connection.py:150-158`]

The entry guard rejects any *foreign* caller while that flag is set:

> ```python
> if self._in_use:
>     raise ConnectionBusyError
> # Reader-lifetime tier: foreign callers are rejected while a reader is live.
> if self._reader_open and not from_reader:
>     raise ConnectionBusyError
> self._in_use = True
> ```
> [VERIFIED: adbc-poolhouse 1.6.1 wheel, `_async/_connection.py:238-245`]

And both close methods take the foreign tier (`from_reader` defaults to `False`):

> `AsyncCursor.close`: `with self._owner._offloading(), anyio.CancelScope(shield=True):`
> [VERIFIED: `_async/_cursor.py:897`]
> `AsyncConnection.close`: `with self._offloading(), anyio.CancelScope(shield=True):`
> [VERIFIED: `_async/_connection.py:701`]

Only the reader's own per-batch pull is exempt, via the single `from_reader=True` call
site [VERIFIED: `_async/_reader.py:281`].

**How to avoid:** Semolina's async cursor close is strictly ordered
`reader → cursor → connection`, and it must run that order even when the caller never
iterated (the reader may have been created lazily and left undrained).

**Warning signs:** `ConnectionBusyError` raised from a `finally`/`__aexit__`; pool
`checkedout()` never returning to 0; a `ResourceWarning` naming
`AsyncRecordBatchReader`.

**Note:** `AsyncConnection.__aexit__` deliberately *bypasses* the guard —
"Bypasses the `_in_use` guard so a connection left marked busy by a failed in-flight
call is still reclaimed" [VERIFIED: `_async/_connection.py:768-769`]. So `async with
conn:` is forgiving where explicit `close()` is not. Since D-08 mandates manual
checkout, Semolina is on the strict path and must respect the ordering.

### Pitfall 2: Breaking cancellation by catching too broadly

**What goes wrong:** ASYNC-06 passes in isolation but a framework timeout leaves the
warehouse query running.

**Why it happens:** On the cancel path `cancellable_offload` swallows the driver's
interrupt and re-raises the framework cancellation:

> "it surfaces an enclosing cancellation if one is pending at the
> `await anyio.sleep(0)` checkpoint ... and otherwise raises
> `get_cancelled_exc_class()`, so a cancelled call can never return `None`/stale
> as though the query had succeeded."
> [VERIFIED: adbc-poolhouse 1.6.1 wheel, `_async/_cancel.py:110-117`]

Under asyncio that exception is `asyncio.CancelledError`, which inherits
`BaseException`, **not** `Exception`. A `try/except Exception` in Semolina would let it
through; a `try/except BaseException` that logs and returns would eat it.

**How to avoid:** The only permitted handler shape is release-and-re-raise. Never
`return` from an `except BaseException` block. Never add `anyio.CancelScope(shield=True)`
(you cannot — ASYNC-05 forbids the import, which is a happy accident).

**Warning signs:** A cancelled `aexecute()` that returns a cursor instead of raising; a
test asserting `pytest.raises(TimeoutError)` that passes for the wrong reason.

### Pitfall 3: `import semolina` breaking for plain (non-async) installs

**What goes wrong:** `pip install semolina && python -c "import semolina"` raises
`ModuleNotFoundError: No module named 'anyio'`, failing ASYNC-04.

**Why it happens:** poolhouse resolves its async entry points lazily *specifically* to
avoid this:

> "Async entry points exposed lazily (PEP 562). Importing them eagerly would pull
> in anyio at `import adbc_poolhouse` time and break the zero-cost sync path
> (PKG-04)"
> [VERIFIED: adbc-poolhouse 1.6.1 wheel, `adbc_poolhouse/__init__.py:67-71`]

A module-level `from adbc_poolhouse import create_async_pool` in Semolina defeats that
protection — the `from ... import` triggers poolhouse's `__getattr__`, which imports
`_async`, which imports anyio. And because `pyproject.toml` sets
`testpaths = ["tests", "src"]` with `--doctest-modules`, pytest imports every `src`
module at collection, so the failure would surface there too.

**How to avoid:** Import `create_async_pool` and `close_async_pool` **inside the function
bodies** that use them — the precedent already exists in this codebase at
`engines/base.py:130-136`, which does `from adbc_poolhouse import close_pool` inside
`dispose()`. Then re-label the resulting `ImportError` to name Semolina's extra rather
than poolhouse's, since poolhouse's own message says
`"pip install adbc-poolhouse[async]"` [VERIFIED: `adbc_poolhouse/__init__.py:108-111`],
which sends the user to the wrong package.

**Warning signs:** The `packaging-smoke` CI job failing; `anyio` appearing in a base
install's `pip list`.

### Pitfall 4: `all` extra silently excluding async from CI

**What goes wrong:** Async tests skip or error in CI while passing locally.

**Why it happens:** All four relevant CI jobs sync with `uv sync --locked --dev --extra
all` [VERIFIED: `.github/workflows/ci.yml:34,55,76,107`], and `all` currently reads
`all = ["semolina[snowflake,databricks,duckdb]"]` [VERIFIED: `pyproject.toml:49-51`] —
no async. anyio is currently present in the venv only as a transitive of the `docs`
group, which CI's test job does not install.

**How to avoid:** Add `async` to the `all` extra **and** add `trio` to
`[dependency-groups] dev`. Do both; `all` alone still leaves Trio missing.

### Pitfall 5: Async examples in docstrings executed as doctests

**What goes wrong:** Collection errors or "coroutine was never awaited" warnings from
`--doctest-modules`.

**Why it happens:** `addopts` includes `--doctest-modules` and `testpaths` includes
`src` [VERIFIED: `pyproject.toml:126-132`]. The project has real executed doctests —
`results.py` uses `.. code-block:: pycon` with `>>>` prompts [VERIFIED:
`src/semolina/results.py:15-19`, `.. code-block:: pycon` followed by `>>> row =
Row({"revenue": 1000, "country": "US"})`]. A `>>> await ...` line cannot run.

**How to avoid:** Async docstring examples use `.. code-block:: python` (never `pycon`,
never `>>>`), which is already the project's documented default in CLAUDE.md.

### Pitfall 6: Assuming TID251 is a text search

**What goes wrong:** A reviewer expects ASYNC-05's check to catch the literal string
`asyncio.` and finds it does not.

**Why it happens:** TID251 is import-graph based. I verified empirically that it flags
`import asyncio`, `import asyncio.tasks`, `from asyncio import gather`, `import anyio`,
`from anyio import to_thread`, and `from anyio.to_thread import run_sync` — six findings
from six lines — but attribute *use* after an import produces no separate diagnostic, and
a docstring mentioning `asyncio.gather` is not flagged at all.

**Why that is the right behaviour:** This phase will write docstrings and comments that
*discuss* asyncio (explaining Posture A). A grep would fail the build on its own
documentation. The semantically meaningful invariant is "no asyncio/anyio in the import
graph", which is what TID251 enforces.

**Residual gap to note honestly:** `importlib.import_module("asyncio")` and
`__import__("asyncio")` bypass TID251. This is not worth defending against; note it in
the plan so ROADMAP SC4's literal wording ("any `asyncio.` reference") is understood as
satisfied in spirit, and consider amending that wording.

### Pitfall 7: A leaked async cursor leaks a pool connection forever

**What goes wrong:** A user who forgets `async with` exhausts the pool.

**Why it happens:** `SemolinaCursor.__del__` currently rescues this — "Best-effort
finalizer that returns a leaked connection to the pool" [VERIFIED:
`src/semolina/cursor.py:295-313`]. The async twin **cannot**: closing requires awaiting,
and poolhouse's own reader finalizer refuses for the same reason —

> "It NEVER calls `self.close()`: an un-awaited coroutine would emit the
> 'coroutine was never awaited' `RuntimeWarning` EDGE-22 forbids."
> [VERIFIED: adbc-poolhouse 1.6.1 wheel, `_async/_reader.py:355-358`]

**How to avoid:** Document `async with` as the canonical form in every docstring and
doc page; consider a warn-only `__del__` on Semolina's async cursor mirroring
poolhouse's. Do **not** claim parity with the sync cursor's safety net.

**Warning signs:** `ResourceWarning: AsyncRecordBatchReader was not closed; use 'async
with await cursor.fetch_record_batch() as reader:'` — a message that leaks a poolhouse
idiom to a Semolina user, which is itself a reason to close readers eagerly.

## Code Examples

### 1. `AsyncEngine.aexecute()` — checkout, execute, hand off (ASYNC-01)

```python
# Every awaited name below verified against adbc-poolhouse 1.6.1 wheel source.
async def aexecute(self, query: _Query) -> AsyncSemolinaCursor:
    builder = self.dialect.create_builder()          # shared with sync path (D-04)
    sql, params = builder.build_select_with_params(query)

    conn = await self._pool.connect()                # AsyncPool.connect is a coroutine
    try:
        cur = conn.cursor()                          # SYNC accessor -- no await
        await cur.execute(sql, params)
    except BaseException:                            # includes CancelledError
        await conn.close()                           # release the slot, then propagate
        raise
    return AsyncSemolinaCursor(cur, conn, self._pool)
```

Source basis for the two non-obvious lines:

> `async def connect(self) -> AsyncConnection:` ... `fairy = await
> offload(self._pool.connect, limiter=self._limiter)`
> [VERIFIED: `_async/_pool.py:89,101`]

> "This is a plain synchronous accessor (NOT `async`): the dbapi `cursor()`
> does no I/O, so there is nothing to offload and no await."
> [VERIFIED: `_async/_connection.py:287-293`]

The `except BaseException: ... raise` shape is copied verbatim in spirit from
`engines/base.py:177-184`. Note `await conn.close()` here is safe because no reader
exists yet on this path.

### 2. Async iteration and the ordered close (ASYNC-03)

```python
async def __anext__(self) -> Row:
    if self._stream_exhausted and self._batch_pos >= len(self._batch_rows):
        raise StopAsyncIteration
    if self._reader is None:
        self._reader = await self._cursor.fetch_record_batch()   # sets _reader_open
    reader = self._reader
    while self._batch_pos >= len(self._batch_rows):
        try:
            batch = await reader.__anext__()      # one offloaded pull, cancellable
        except StopAsyncIteration:
            self._stream_exhausted = True
            raise
        if batch.num_rows == 0:
            continue
        self._batch_rows = batch.to_pylist()
        self._batch_pos = 0
    row = Row(self._batch_rows[self._batch_pos])
    self._batch_pos += 1
    return row


async def aclose(self) -> None:
    """Close in the ONE order poolhouse permits: reader -> cursor -> connection."""
    if self._closed:
        return
    self._closed = True
    if self._reader is not None:
        with contextlib.suppress(Exception):     # never mask the caller's error
            await self._reader.close()           # clears _reader_open (idempotent)
    with contextlib.suppress(Exception):
        await self._cursor.close()               # would raise while reader was open
    with contextlib.suppress(Exception):
        await self._conn.close()                 # no-op if already invalidated
```

This mirrors `cursor.py:238-285` as D-07 requires, with three substitutions:
`read_next_batch()` → `await reader.__anext__()`, `StopIteration` →
`StopAsyncIteration`, and the sync `OSError` normalisation dropped because poolhouse
converts end-of-stream itself:

> "The worker catches the driver's end-of-stream `StopIteration` and returns the
> module-level `_EXHAUSTED` sentinel instead --- a bare `StopIteration` crossing
> `anyio.to_thread.run_sync` becomes a `RuntimeError` under both asyncio and trio,
> so it must never leak (D-29-05)."
> [VERIFIED: `_async/_reader.py:19-22`]

`reader.close()` is idempotent and clears the lock even on failure
[VERIFIED: `_async/_reader.py:314-323` — `if self._detached: return` then
`finally: self._owner._reader_open = False`], and close-after-invalidate is documented
safe [VERIFIED: `_async/_connection.py:728-730` — "A `close()` after an `invalidate()`
is a safe no-op (probe-confirmed)"], which together discharge D-10.

`contextlib.suppress(Exception)` is deliberately narrower than `BaseException` here so a
cancellation arriving during teardown still propagates (Pitfall 2).

### 3. `_Query.aexecute()` (ASYNC-02)

```python
async def aexecute(self) -> AsyncSemolinaCursor:
    from .registry import get_async_engine

    self._validate_for_execution()
    engine = get_async_engine(self._using)
    return await engine.aexecute(self)
```

A direct transliteration of `query.py:414-419`, which reads
`from .registry import get_engine` / `self._validate_for_execution()` /
`engine = get_engine(self._using)` / `return engine.execute(self)`. Because the
registries are separate (D-05), `.using("reports")` resolves against the async registry
here and the sync registry in `execute()` — the same name may legitimately hold both.

### 4. `create_async_engine()` and the DuckDB listener target

```python
def create_async_engine(                      # SYNC def -- see Pattern 1
    config: WarehouseConfig | str = "default",
    *,
    config_path: str | Path = ".semolina.toml",
) -> AsyncEngine:
    try:
        from adbc_poolhouse import create_async_pool      # deferred: Pitfall 3
    except ImportError as exc:
        raise ImportError(
            "Async support requires the optional async dependencies. "
            "Install them with: pip install 'semolina[async]'"
        ) from exc

    if isinstance(config, str):
        wh_config, dialect = _read_connection(config, config_path)
    else:
        wh_config = _expand_private_key_path(config)
        dialect = _dialect_for_config_type(config)

    pool = create_async_pool(wh_config)

    if dialect is Dialect.DUCKDB:
        from sqlalchemy import event

        # AsyncPool is NOT a SQLAlchemy event target; the listener must attach to
        # the inner sync QueuePool it wraps.  See Finding 4.
        event.listen(pool._pool, "connect", _load_semantic_views)

    return AsyncEngine(pool=pool, dialect=resolve_dialect(dialect), config=wh_config)
```

Structurally identical to `config.py:223-238`, which reads `pool = create_pool(wh_config)`
then `event.listen(pool, "connect", _load_semantic_views)`.

### 5. The Posture A lint gate (ASYNC-05) — executed and verified

```toml
[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "TCH", "D", "TID"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"asyncio".msg = "Posture A (ASYNC-05): Semolina library code must stay loop-agnostic. Await adbc-poolhouse primitives instead."
"anyio".msg = "Posture A (ASYNC-05): Semolina must not import anyio. Use a bare `async def` with neutral awaits."

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["TID251"]          # D-14: the Trio half of the matrix needs anyio
```

Executed this session against a fixture tree with an identical file in `src/semolina/`
and in `tests/`:

```
$ .venv/bin/python -m ruff check --no-cache --output-format concise .   # ruff 0.15.x
src/semolina/a.py:1:8: TID251 `asyncio` is banned: Posture A (ASYNC-05)...
src/semolina/a.py:2:8: TID251 `asyncio` is banned: ...   # import asyncio.tasks
src/semolina/a.py:3:1: TID251 `asyncio` is banned: ...   # from asyncio import gather
src/semolina/a.py:4:8: TID251 `anyio` is banned: ...
src/semolina/a.py:5:1: TID251 `anyio` is banned: ...     # from anyio import to_thread
src/semolina/a.py:6:1: TID251 `anyio` is banned: ...     # from anyio.to_thread import run_sync
Found 6 errors.                                          # tests/a.py: 0 findings

$ uvx ruff@0.9.6 check --no-cache --output-format concise .   # the pre-commit pin
src/semolina/a.py:1:8: TID251 `asyncio` is banned: Posture A (ASYNC-05).
src/semolina/a.py:2:1: TID251 `anyio` is banned: Posture A (ASYNC-05).
Found 2 errors.
```

Both ruff versions in play accept the config and behave identically. The two-version
check matters: the dev dependency is `ruff>=0.15.1` [VERIFIED: `pyproject.toml:67`] but
the pre-commit hook pins `rev: v0.9.6` [VERIFIED: `.pre-commit-config.yaml:15-16`], so a
config that worked in only one would pass `just`-driven checks and fail `prek`, or the
reverse.

### 6. The asyncio + Trio matrix (D-17)

```python
# tests/unit/test_async_query.py  (module-local, so other test modules are unaffected)
import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request):
    return request.param


async def test_aexecute_streams_rows(async_duckdb_engine):
    ...
```

[CITED: github.com/agronholm/anyio/blob/master/docs/testing.md — "Use the
`pytest.mark.anyio` marker on modules, classes, or functions to enable AnyIO's
asynchronous test runner"; and the `@pytest.fixture(params=[...])
def anyio_backend(request): return request.param` pattern for multi-backend runs]

Prefer the module-local `pytestmark` + local `anyio_backend` fixture over the
`anyio_mode = "auto"` ini option (which does exist in the installed 4.13.0
[VERIFIED: `anyio/pytest_plugin.py:76-77,89` — `parser.addini("anyio_mode", ...)` and
`config.getini("anyio_mode") == "auto"`]). Auto mode is repository-wide, and this
repository collects `src` under `--doctest-modules`; scoping the marker to the async test
modules keeps the blast radius at zero.

### 7. Reusing an existing cassette without recording (D-16 spike)

```python
@pytest.mark.adbc_cassette("async_single_metric_snowflake")
async def test_async_replays_existing_cassette(snowflake_async_engine): ...
```

```bash
# One-time, offline: copy a recorded cassette to the named path.
cp -R tests/integration/cassettes/integration/test_queries/\
test_single_metric_snowflake_engine_/adbc_driver_snowflake.dbapi \
   tests/integration/cassettes/async_single_metric_snowflake/adbc_driver_snowflake.dbapi
```

A positional marker argument replaces node-id derivation entirely:

> ```python
> marker = item.get_closest_marker("adbc_cassette")
> if marker is not None:
>     resolved_dialect = marker.kwargs.get("dialect", resolved_dialect)
>     if marker.args:
>         # Named cassette: cassette_dir / name / driver_module_name
>         cassette_path = self.cassette_dir / str(marker.args[0]) / driver_module_name
> ```
> [VERIFIED: installed `pytest_adbc_replay/_session.py:215-220`]

Cassettes are plain, copyable directories — a Snowflake one contains exactly
`000_query.sql`, `000_params.json`, `000_result.arrow` [VERIFIED: `ls` of
`tests/integration/cassettes/integration/test_queries/test_single_metric_snowflake_engine_/adbc_driver_snowflake.dbapi`].
Databricks cassettes carry one extra `databricks/` differentiator segment under the
driver directory, which a copy must preserve.

Because the async path reuses `build_select_with_params` unchanged (D-04), the SQL the
driver receives is byte-identical, so the copied cassette matches. This also solves the
parametrization problem: without an explicit name, the `[asyncio]` and `[trio]` variants
would derive two different cassette paths from their node ids and each need its own
recording.

## Runtime State Inventory

Not applicable — this phase is purely additive (new modules, a new extra, a new lint
rule) with no rename, refactor, or migration. The one pre-existing value it mutates is
`.planning/config.json`'s `git.branching_strategy` (TOOL-01), which is planning metadata,
not runtime state.

One behavioural change does ride along with the dependency bump and is **not** additive:
see Finding 1's second half on sync `pool_size` semantics.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Users hand-wrap `.execute()` in `run_in_executor` / `anyio.to_thread` | `await engine.aexecute(query)` | This phase | Executor sizing stops being the user's problem |
| Async DB access requires an async driver (`asyncpg`, `psycopg` async) | Thread-offload over GIL-releasing native calls | poolhouse 1.5.0, 2026-07 | Legitimate because ADBC wraps native calls in `with nogil:`; no async C API exists or is planned |
| Trio compatibility claimed by inspection | Verified: one `anyio.to_thread.run_sync` chokepoint, zero asyncio | Verified this session | The precondition the source todo flagged "unverified" is now closed |
| poolhouse tuning args hard-coded (`pool_size=5`) in `create_async_pool` | `_resolve_tuning(config, ...)` honours the config's own fields | **poolhouse 1.6.0** | Drives the floor-pin correction, Finding 1 |
| Cassette paths derived from node ids only | `@pytest.mark.adbc_cassette("name")` overrides the path | pytest-adbc-replay 1.1.x | Makes offline cassette reuse and backend parametrization tractable |

**Deprecated/outdated:**

- `adbc-poolhouse` 1.3.1 (installed) and 1.4.0: no async surface at all — the `_async`
  subpackage first appears in 1.5.0 [VERIFIED: wheel contents of 1.5.0 vs the installed
  1.3.1 tree].
- `adbc-poolhouse` 1.5.0/1.5.1 for async use: superseded by 1.6.0's tuning resolution.
- The `Engine.aexecute` code sketch in
  `.planning/todos/pending/2026-02-23-async-query-interface-for-fastapi-and-async-frameworks.md`:
  superseded by D-09 and independently wrong per Anti-Patterns.

## Detailed Findings

### Finding 1 — The ASYNC-04 version floor is wrong; use `>=1.6.1` (HIGH)

In 1.5.0 and 1.5.1, `create_async_pool` declares hard defaults and passes them straight
through, ignoring the config object's own tuning fields:

```python
# adbc-poolhouse 1.5.0, _async/_factory.py
    pool_size: int = 5,
    max_overflow: int = 3,
    ...
    sync_pool = _create_pool_impl(config, driver_path, db_kwargs, entrypoint,
                                  dbapi_module, pool_size, max_overflow, ...)
    return AsyncPool(sync_pool, pool_size=pool_size, max_overflow=max_overflow)
```

1.6.x replaces those with `None` sentinels resolved against the config:

```python
# adbc-poolhouse 1.6.1, _async/_factory.py
from adbc_poolhouse._pool_factory import _create_pool_impl, _resolve_tuning
    pool_size: int | None = None,
    ...
    r_pool_size, r_max_overflow, r_timeout, r_recycle, r_pre_ping = _resolve_tuning(
        config, pool_size, max_overflow, timeout, recycle, pre_ping
    )
```

`_resolve_tuning` does not exist anywhere in 1.5.0 [VERIFIED: `grep -c "_resolve_tuning"
v1.5.0/.../_pool_factory.py` → `0`].

**Why this bites Semolina specifically.** `DuckDBConfig.pool_size` defaults to 1 for
`:memory:` and the config actively forbids raising it:

> ```python
> if self.database == ":memory:" and self.pool_size > 1:
>     raise ConfigurationError(
>         'pool_size > 1 with database=":memory:" will give each pool '
>         "connection an isolated in-memory database ..."
>     )
> ```
> [VERIFIED: adbc-poolhouse 1.6.1 wheel, `_duckdb_config.py:118-127`]

On 1.5.x, `create_async_pool(DuckDBConfig(database=":memory:", pool_size=1))` would build
a pool of 5 anyway — producing exactly the isolated-database failure that validator
exists to prevent, and doing so silently.

**The bump is not purely additive.** `_resolve_tuning` was added to the *shared*
`_pool_factory`, so the synchronous `create_pool` gains config-honouring too. The
installed 1.3.1 sync `create_pool` also hard-codes `pool_size: int = 5` [VERIFIED:
`.venv/.../adbc_poolhouse/_pool_factory.py:115,129,142,157`], which means the five
existing call sites that pass `DuckDBConfig(database=":memory:", pool_size=1)` —
`src/semolina/conftest.py:113`, `tests/conftest.py:132`,
`tests/unit/test_duckdb_engine.py:73,127`, `tests/unit/test_query.py:72`,
`tests/unit/test_pool.py:105,234,378,440` — currently get 5 isolated in-memory databases
and will get 1 after the bump. They pass today only because the `connect` event listener
re-seeds data on every physical connection. The change is an improvement and should be
harmless, but `tests/unit/test_pool.py:367` reasons explicitly about pool_size=1
semantics ("With ``pool_size=1`` a...") and must be re-read.

**Recommendation:** bump the base pin to `adbc-poolhouse>=1.6.1` as well as the extra,
so sync and async agree, and give the floor-bump task an explicit verification step
covering the existing DuckDB pool tests. Amend ASYNC-04's text from `>=1.5.0` to
`>=1.6.1`.

### Finding 2 — poolhouse delivers 100% of ASYNC-06 (HIGH)

`cancellable_offload` pairs a watcher task parked on an `anyio.Event` with the worker:

> ```python
> except get_cancelled_exc_class():
>     if worker_started:
>         with anyio.CancelScope(shield=True):
>             adbc_cancel()  # thread-safe; unblocks the worker, fires ONCE
>             aborted_by_us = True
>             if on_abort is not None:
>                 ...
>                 await on_abort()  # poison recovery (D-25-03), shielded
>     raise  # never swallow the cancellation (D-25-06)
> ```
> [VERIFIED: adbc-poolhouse 1.6.1 wheel, `_async/_cancel.py:182-200`]

Every result-producing `AsyncCursor` method routes through it with
`on_abort=self._owner.invalidate` [VERIFIED: `_async/_cursor.py:236,266,289,321,328,351,381,868`],
including `fetch_record_batch`, and each reader pull does too
[VERIFIED: `_async/_reader.py:282-290`]. `adbc_cancel` resolution tolerates a cursor
lacking the method [VERIFIED: `_async/_cursor.py:172-174` — `cancel = getattr(self._cursor,
"adbc_cancel", None)` / `if cancel is not None: cancel()`].

Semolina's contribution to ASYNC-06 is therefore zero lines of cancellation logic and one
discipline: don't break transparency (Pitfall 2). Plan the ASYNC-06 task as a *test* task,
not an implementation task.

### Finding 3 — `AsyncEngine.dispose()` must be async, and `registry.reset()` cannot be (HIGH)

`close_async_pool` is a coroutine [VERIFIED: `_async/_factory.py` —
`async def close_async_pool(pool: AsyncPool) -> None:` ... `await pool.close()`], and
`AsyncPool.close` shields its offloaded teardown [VERIFIED: `_async/_pool.py:113-114` —
`with anyio.CancelScope(shield=True): await offload(close_pool, self._pool,
limiter=self._limiter)`].

Two consequences:

1. `Engine.dispose()`'s existing branch cannot be reused. It keys on
   `hasattr(pool, "_adbc_source")` [VERIFIED: `src/semolina/engines/base.py:131`], and
   that marker is set on the *inner sync* pool [VERIFIED: `_pool_factory.py:164` —
   `pool._adbc_source = source  # type: ignore[attr-defined]`], so the check is `False`
   for an `AsyncPool` and would fall through to a bare `pool.close()` — which on
   `AsyncPool` returns an un-awaited coroutine and closes nothing.
2. `registry.reset()` is synchronous and autouse-invoked after every test
   [VERIFIED: `src/semolina/registry.py:94-110` and `tests/conftest.py:43-49`, which
   yields then calls `registry.reset()`]. It cannot `await`.

**Recommendation:** give `AsyncEngine` an `async def dispose()` calling
`await close_async_pool(self._pool)` for users, and have the synchronous `reset()`
tear async engines down directly with `close_pool(engine._pool._pool)` — which is
literally the same call `AsyncPool.close` offloads, just run inline where there is no
loop. Flag this in the plan; it is easy to miss until the autouse fixture starts leaking
pools between tests.

### Finding 4 — DuckDB's `semantic_views` listener must attach to the inner pool (HIGH)

`AsyncPool` is a plain wrapper, not a SQLAlchemy pool: `self._pool = sync_pool`
[VERIFIED: `_async/_pool.py:84`], and `DuckDBConfig` exposes no extension-loading field
[VERIFIED: `_duckdb_config.py:31-46` — the only fields are `database`, `pool_size`,
`read_only`]. So `event.listen(async_pool, "connect", ...)` has no valid target and
`create_async_engine` must reach the wrapped `QueuePool` as `pool._pool`.

Double-private access is unattractive but consistent with the repo, which already does
`event.listen(engine._pool, "connect", _setup_sales_data)` in
`tests/conftest.py:133`, and `reportPrivateUsage = false` is set project-wide
[VERIFIED: `pyproject.toml:83`], with `SLF` absent from the ruff `select` list. Add a
comment explaining why, and consider filing an upstream request for a public accessor —
the same private reach is needed by any consumer wiring a connect event to an async pool.

### Finding 5 — `AsyncPool`/`AsyncCursor`/`AsyncRecordBatchReader` are not public names (MEDIUM)

poolhouse's `__all__` exports only the three factory functions among async names
[VERIFIED: `adbc_poolhouse/__init__.py:39-65` — `"close_async_pool"`,
`"create_async_pool"`, `"managed_async_pool"` are present; no `Async*` class is], and
`_async/__init__.py`'s `__all__` is the same three. The reader module says so explicitly:
"never constructed by users, so it stays out of `_async/__init__.py`'s `__all__`, exactly
like `AsyncCursor`" [VERIFIED: `_async/_reader.py:7-8`].

So annotate them as `Any`, following the established in-repo convention and its recorded
rationale [VERIFIED: `src/semolina/engines/base.py:70-72` — "pool: The adbc-poolhouse
connection pool this engine owns. Typed as ``Any`` because the poolhouse/SQLAlchemy pool
surface is untyped."]. Do not import from `adbc_poolhouse._async._pool` to get a name —
that would both reach into a private module and defeat the lazy-import protection of
Pitfall 3. This keeps basedpyright strict satisfied with no `# type: ignore`.

### Finding 6 — `trio` is a separate dependency (HIGH)

`adbc-poolhouse[async]` declares only `anyio>=4.13; extra == "async"` [VERIFIED: PyPI
`requires_dist` for 1.6.1]. anyio's Trio backend requires `trio` itself to be installed;
it is not vendored. Combined with Pitfall 4, the D-17 matrix needs **two** packaging
edits (`all` gains `async`; dev gains `trio`), and a plan that makes only the first will
see the `[trio]` half of every parametrized test error at setup.

### Finding 7 — Concurrency tests need the file-backed DuckDB fixture (MEDIUM)

Proving "the event loop stays free" (SC1) needs more than one usable connection over
shared data. In-memory DuckDB cannot provide that: `pool_size` is pinned to 1 and raising
it is a `ConfigurationError` (quoted in Finding 1). A file-backed database defaults to 5:

> "if "pool_size" not in self.model_fields_set and self.database != ":memory:":
>     self.pool_size = 5"
> [VERIFIED: adbc-poolhouse 1.6.1 wheel, `_duckdb_config.py:113-115`]

The repo already has the right substrate: a session-scoped `duckdb_file_backed_db`
fixture that provisions `sales_data` + `sales_view` in a `tmp_path_factory` directory
[VERIFIED: `tests/conftest.py:141-179`]. Build the async concurrency fixture on it rather
than on `duckdb_pool`.

### Finding 8 — Cancellation is not testable through cassettes (MEDIUM)

`ReplayCursor.adbc_cancel()` is a deliberate no-op in replay mode:

> ```python
> if self._mode == "none":
>     return  # replay: nothing is running
> ```
> [VERIFIED: installed `pytest_adbc_replay/_cursor.py:399-410`]

Which is correct — but it means a replay-backed test can never observe a genuine abort,
and replay returns instantly so no cancellation can land mid-flight anyway. poolhouse
anticipates precisely this case: "a replay/cassette backend that does not block (and so
never aborts mid-flight) need not provide it" [VERIFIED: `_async/_cursor.py:166-168`].

**Therefore:** the ASYNC-06 test must run against a real driver with a genuinely
long-running query. DuckDB is the right choice and the upstream precedent —
poolhouse's own probe records that the aborted worker "raises
`ProgrammingError("...INTERRUPT Error: Interrupted!")`" [VERIFIED:
`_async/_cancel.py:104-106`]. Expect the driver's interrupt to be swallowed and a
cancellation re-raised instead, so assert on cancellation/timeout, not on
`ProgrammingError`.

### Finding 9 — Replay interception is confirmed sync and async-transparent (HIGH)

Three independent confirmations of D-15, promoting it from structural inference to
verified:

1. The patch point is a module attribute, upstream of everything async:
   `setattr(driver_mod, "connect", _make_patched(driver_name, original_connect))`
   [VERIFIED: installed `pytest_adbc_replay/plugin.py:334`]. Module attributes are
   process-global, so the patch is visible from poolhouse's offload worker thread.
2. The package contains no async code at all — `grep -rn "async def\|await "` over
   `pytest_adbc_replay/*.py` returns nothing; the only concurrency construct is
   `_ITEM_LOCK = threading.Lock()` at `plugin.py:33`, and there is no thread-local state
   that would break under offload.
3. `ReplayCursor.fetch_record_batch(self) -> pa.RecordBatchReader` returns a real Arrow
   reader [VERIFIED: `pytest_adbc_replay/_cursor.py:558-560`], which structurally
   satisfies poolhouse's `_SyncReader` protocol (`schema` / `read_next_batch` / `close`)
   [VERIFIED: `_async/_reader.py:73-86`].

D-16's spike is still worth keeping as Task 1 — it converts three static confirmations
into one executed test — but it is now expected to pass, not a genuine gate. No
`pytest-adbc-replay` update is needed.

### Finding 10 — "the same result surface" needs interpreting (MEDIUM)

ASYNC-01 says `aexecute()` returns "the same result surface as `.execute()`". Strict
sameness is impossible: on `AsyncCursor`, `fetchall`/`fetchone`/`fetchmany`/
`fetch_arrow_table` are all coroutines [VERIFIED: `_async/_cursor.py:331,269,292,354`
are each `async def`], so Semolina's `fetchall_rows()` twin must be awaited. What *is*
identical: `description`, `rowcount`, and `arraysize` remain synchronous property reads
[VERIFIED: `_async/_cursor.py:175,187,198` — plain `@property`], as does the reader's
`schema` [VERIFIED: `_async/_reader.py:219-229`], so `_column_names()` needs no change
and `Row` construction is unchanged. Read the requirement as "the same shape and the same
`Row` type, with awaited fetches", and say so in the plan so the verifier does not chase
an impossible literal reading.

## Project Constraints (from CLAUDE.md)

| Directive | Bearing on this phase |
|-----------|----------------------|
| `prek run --all-files` before committing (ruff lint+format, basedpyright strict, shellcheck) | The new `TID` rule joins this gate. `prek` uses ruff **v0.9.6**; the dev dep is 0.15.x — config verified on both (Code Examples §5) |
| `just test` = `uv run pytest` + jaffle-shop | Async tests land in the default run. `--doctest-modules` over `src` applies (Pitfall 5) |
| `just docs-build` (Sphinx `-W`, warnings are errors) | Any new docstring or doc page must build clean under `-W` |
| Avoid `# type: ignore`; solve the typing issue; pyproject exemptions last resort | Discharged by typing the poolhouse surface as `Any` per Finding 5 — the existing, documented convention. No new exemptions needed |
| Bug fixes: failing test first, then the fix, as separate commits | Applies to any bug found; note the standing Phase 45 caveat that basedpyright strict rejects tests referencing not-yet-existent attributes, so RED+GREEN may land together per task |
| Docs: load `@.claude/skills/semolina-docs-author/SKILL.md` for new pages / major rewrites; **add it to `<execution_context>` of any PLAN.md with doc tasks** | Required. `web-api.rst` gains an async section; `streaming.rst` and `connection-pools.rst` likely too |
| API surface changes must update corresponding docs (mandatory) | This phase adds public API (`create_async_engine`, async registry, `aexecute`), so doc updates are mandatory, not optional |
| Diataxis placement; how-to = illustrative snippets, tutorials = runnable | Async guidance belongs in `how-to/` (reader supplies the app); no new tutorial required |
| Line length 100; D213; multi-line docstring quotes on own lines; `.. code-block:: python` in `Example:` (never markdown fences) | Standard; see Pitfall 5 for the `pycon`-vs-`python` trap |
| Audience: data/analytics engineers building a BI backend; warm-but-efficient; second person | The async surface is squarely for this audience — it is the FastAPI-backend enabler |
| Verify library/API claims against latest official docs, not repo style (standing rule, `feedback_verify_claims_official_docs`) | Honoured: the entire poolhouse async API was read from the 1.6.1 wheel, and the anyio pytest patterns from anyio's own `docs/testing.md` |

Docs pages to touch (from the existing tree):

- `docs/src/how-to/web-api.rst` — currently shows only sync `def` endpoints
  [VERIFIED: `docs/src/how-to/web-api.rst:71-81` defines `@app.get("/api/sales")` /
  `def get_sales():` calling `.execute()`]. Add an `async def` section; keep the sync
  form documented, since FastAPI runs `def` handlers in a threadpool and that remains
  correct.
- `docs/src/how-to/streaming.rst` — add the `async for row in cursor` form and the
  mandatory `async with`.
- `docs/src/how-to/connection-pools.rst` — it already documents config-driven
  `pool_size`, which only becomes true for pools built via poolhouse ≥1.6.0. Worth a
  consistency read after the bump (Finding 1).
- `docs/src/tutorials/installation.rst` — document the `[async]` extra.

## Runtime / Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `adbc-poolhouse` async surface | everything in the phase | ✗ (installed 1.3.1 has no `_async`) | 1.3.1 installed; 1.6.1 on PyPI | none — the floor bump is the gating task (D-11) |
| `anyio` | poolhouse offload (transitive) | ✓ | 4.13.0 | none needed |
| `trio` | D-17 Trio matrix half | ✗ | 0.33.0 on PyPI | none — must be added to dev |
| `pytest-adbc-replay` | Snowflake/Databricks async tests | ✓ | 1.1.1 (= latest) | none needed; no update required (Finding 9) |
| `adbc_driver_duckdb` + `semantic_views` extension | DuckDB async unit/cancellation tests | ✓ (guarded by `pytest.importorskip`) | duckdb pinned `==1.5.3` | `importorskip` already in use at `tests/conftest.py:125` |
| `adbc_driver_snowflake` | replay of Snowflake cassettes | ✓ via `[snowflake]` extra | — | cassettes only; no credentials needed |
| Databricks ADBC driver (Foundry) | live Databricks async verification | ✗ on PyPI | — | cassette replay (copied per Code Examples §7) — the only path, as CONTEXT.md notes |
| Python | test matrix | ✓ | 3.14.2 in venv; CI runs 3.11 + 3.14 | trio and anyio both support 3.11–3.14 |

**Missing dependencies with no fallback:** the `adbc-poolhouse` floor bump and `trio`.
Both are ordinary `uv add` operations, not blockers — but they gate everything else, which
is exactly why D-11 sequences the bump first.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 + the anyio pytest plugin (auto-registered) + pytest-xdist + syrupy |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests", "src"]`, `--doctest-modules`) |
| Quick run command | `uv run pytest tests/unit/test_async_engine.py tests/unit/test_async_cursor.py -x` |
| Full suite command | `just test` (= `uv run pytest` then jaffle-shop's `uv run pytest`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| ASYNC-01 | `await engine.aexecute(q)` returns rows; loop stays free | unit | `uv run pytest tests/unit/test_async_engine.py -x` | ❌ Wave 0 |
| ASYNC-01 | Loop non-blocking under concurrency (file-backed DuckDB, Finding 7) | unit | `uv run pytest tests/unit/test_async_engine.py -k concurrency -x` | ❌ Wave 0 |
| ASYNC-02 | `await Sales.query()...aexecute()` | unit | `uv run pytest tests/unit/test_async_query.py -x` | ❌ Wave 0 |
| ASYNC-03 | `async for row in cursor` streams `Row` batch by batch, no whole-table materialization | unit | `uv run pytest tests/unit/test_async_cursor.py -k stream -x` | ❌ Wave 0 |
| ASYNC-03 | Close order reader→cursor→conn; no `ConnectionBusyError`; pool `checkedout()` back to 0 | unit | `uv run pytest tests/unit/test_async_cursor.py -k close -x` | ❌ Wave 0 |
| ASYNC-04 | `[async]` extra resolves; base install pulls no anyio | integration (CI job) | `uv pip install --python /tmp/smoke/bin/python "." && /tmp/smoke/bin/python -c "import semolina, importlib.util; assert importlib.util.find_spec('anyio') is None"` | ❌ Wave 0 (extend `ci.yml` `packaging-smoke`, pattern at `ci.yml:149-169`) |
| ASYNC-05 | No asyncio/anyio import in `src/semolina/` | lint | `uv run ruff check src/semolina` (TID251) | ✅ ruff configured; rule ❌ Wave 0 |
| ASYNC-05 | Async tests green under asyncio **and** Trio | unit (parametrized) | `uv run pytest tests/unit -k "async and trio" -x` | ❌ Wave 0 |
| ASYNC-06 | Cancellation reaches the driver via `adbc_cancel` | unit (real DuckDB, Finding 8) | `uv run pytest tests/unit/test_async_cancel.py -x` | ❌ Wave 0 |
| ASYNC-01/03 | Snowflake + Databricks dialects replay through the async path | integration (cassette) | `uv run pytest tests/integration -k async` | ❌ Wave 0 (named cassettes copied, Code Examples §7) |
| TOOL-01 | `git.branching_strategy == "milestone"` | manual/inspection | `python -c "import json;assert json.load(open('.planning/config.json'))['git']['branching_strategy']=='milestone'"` | n/a — config assertion |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit -k async -x` plus `prek run --all-files`
  (which now includes the TID251 gate).
- **Per wave merge:** `just test`.
- **Phase gate:** full suite green, `just docs-build` clean under `-W`, and the
  `packaging-smoke` job's base-install assertion passing, before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `pyproject.toml` — `[async]` extra, `all` includes `async`, dev gains `trio`, base
      pin → `>=1.6.1`, `TID` in `select` + `banned-api` + `per-file-ignores` (gates
      everything; D-11)
- [ ] `tests/unit/test_async_engine.py` — covers ASYNC-01
- [ ] `tests/unit/test_async_cursor.py` — covers ASYNC-03 (streaming + close ordering)
- [ ] `tests/unit/test_async_query.py` — covers ASYNC-02
- [ ] `tests/unit/test_async_cancel.py` — covers ASYNC-06 (real DuckDB, long query)
- [ ] `tests/conftest.py` — `async_duckdb_engine` fixture on the existing
      `duckdb_file_backed_db`; async-aware `registry.reset()` teardown (Finding 3)
- [ ] Per-module `anyio_backend` parametrized fixtures — covers the ASYNC-05 loop matrix
- [ ] `tests/integration/` — `snowflake_async_engine` / `databricks_async_engine`
      fixtures + named cassette copies
- [ ] `.github/workflows/ci.yml` — extend `packaging-smoke` with the base-install
      no-anyio assertion (ASYNC-04)

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No change — credentials continue to flow through poolhouse config objects; this phase adds no auth path |
| V3 Session Management | no | No user sessions |
| V4 Access Control | no | Warehouse-side; unchanged |
| V5 Input Validation | yes (unchanged) | The async path reuses `build_select_with_params()` byte-identically (D-04), so the Phase 45 literal-escaping and parameterization controls apply verbatim. **Adding no second SQL path is itself the security control here** |
| V6 Cryptography | no | None introduced; `_expand_private_key_path` reuse is unchanged |
| V7 Error handling / logging | yes | New failure mode `ConnectionBusyError` must produce an actionable message without leaking connection internals; the re-labelled async `ImportError` must not echo config values |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Connection-pool exhaustion via unbounded concurrent requests | Denial of Service | Already bounded upstream: one dedicated `anyio.CapacityLimiter(pool_size + max_overflow)` per pool, "never anyio's global 40-token default" [VERIFIED: `_async/_pool.py:5-9`]. Semolina must not add a second, larger bound |
| Leaked connections exhausting the pool over time | Denial of Service | Ordered close (Pitfall 1) + documented `async with`; **note the honest gap** that no `__del__` rescue is possible (Pitfall 7) |
| Abandoned warehouse queries after client disconnect (cost + resource burn) | Resource exhaustion | `adbc_cancel` via `cancellable_offload` — this is what ASYNC-06 buys, and it is a real cost control on metered warehouses, not just tidiness |
| Cross-task connection aliasing corrupting a transaction | Tampering | `ConnectionBusyError` rejects rather than serializes, "which would still let two tasks' statements interleave inside one transaction (driver-safe, logically corrupt) and hide the bug" [VERIFIED: `_exceptions.py:34-41`] |
| Credential leakage into cassettes | Information Disclosure | Unchanged: `adbc_scrub_keys = ["password", "token", "access_token"]` [VERIFIED: `pyproject.toml:158-162`]. The Code Examples §7 approach copies existing cassettes and records nothing new, so it adds no exposure |
| Supply chain: new optional dependency | Tampering | `anyio` is declared by poolhouse itself, not chosen by Semolina; `trio` is dev-only. See Package Legitimacy Audit |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The five existing `DuckDBConfig(..., pool_size=1)` test call sites still pass once 1.6.0+ actually honours `pool_size=1`. I reasoned this from the per-connection `connect` listener but did not run the suite against 1.6.1 (not installed) | Finding 1 | Low–medium. Some DuckDB pool tests may need adjustment; the floor-bump task should run the full suite as its verification step |
| A2 | The SQL the async path sends is byte-identical to the sync path, so a copied cassette matches. Follows from D-04 and from Phase 44 Plan 05's evidence that the engine refactor left SQL byte-identical, but not executed for the async path | Code Examples §7, Finding 9 | Low. The D-16 spike is precisely the test that closes this; if it fails, cassettes must be recorded against live Snowflake instead |
| A3 | A long-running DuckDB query is a reliable cancellation substrate under both asyncio and Trio | Finding 8 | Medium. poolhouse's own probe used DuckDB, so the mechanism is proven; test *timing* may still be flaky. Plan a generous, deterministic query rather than a sleep-based race |
| A4 | `AsyncEngine` needs no per-backend subclasses because `introspect()` is the only abstract method and async introspection is deferred | Architecture Patterns | Low. If a backend hook turns out to be needed, adding subclasses later is additive |
| A5 | Reaching `pool._pool` for the DuckDB connect listener is acceptable rather than requiring an upstream change first | Finding 4 | Low. It works and is precedented in-repo; the cost is coupling to a private attribute that a future poolhouse release could rename |
| A6 | The recommended async registry names (`register_async` / `get_async_engine` / `unregister_async`) are a suggestion only — D-05 leaves naming to the planner | Recommended Project Structure, Code Examples §3 | None. Explicitly discretionary |

## Open Questions (RESOLVED)

All five were settled at plan time (2026-08-01). Q2 was decided by the user; Q1, Q3, Q4
and Q5 fall under CONTEXT.md's "Claude's Discretion" and were adopted as recommended.

| # | Resolution | Settled in |
|---|-----------|------------|
| 1 | Same names, awaited (`await cur.fetchall_rows()`) — no `a`-prefixed twins | `46-02-PLAN.md` `interface_contract` |
| 2 | **Amend to `>=1.6.1`** in REQUIREMENTS.md + ROADMAP.md, with the `_resolve_tuning` evidence note (user decision) | `46-01-PLAN.md` Task 3 |
| 3 | `all` extra includes `async` | `46-01-PLAN.md` |
| 4 | `fetch_arrow_table()` async twin pulled forward | `46-02-PLAN.md` |
| 5 | `ConnectionBusyError` propagates unwrapped; documented | `46-02-PLAN.md` |

1. **How literally should ASYNC-01's "same result surface" be read?** — RESOLVED: same names, awaited.
   - What we know: `description`, `rowcount`, `arraysize`, and `reader.schema` stay
     synchronous; all fetch methods become coroutines (Finding 10).
   - What's unclear: whether the async twin should be `await cur.fetchall_rows()`
     (same name, awaited) or `await cur.afetchall_rows()` (distinct name).
   - Recommendation: same names, awaited — the type is already distinct per D-06, so
     there is no ambiguity to disambiguate, and it keeps the two surfaces readable
     side by side. Flag for the planner to confirm.

2. **Should ASYNC-04's `>=1.5.0` be amended in REQUIREMENTS.md?**
   - What we know: 1.5.0 is functionally wrong for Semolina's DuckDB config (Finding 1).
   - What's unclear: whether the requirement text is treated as immutable.
   - Recommendation: amend to `>=1.6.1` and record the reason, as Phase 42/43 amended
     ROADMAP criteria on evidence. Shipping a pin known to misconfigure pools to satisfy
     a requirement's wording would be the wrong trade.

3. **Does the `all` extra include `async`?**
   - What we know: CI depends on `--extra all`, so if `all` excludes async the tests
     cannot run there (Pitfall 4). CONTEXT.md lists this as an open packaging decision.
   - Recommendation: include it. `all` reads as "everything optional", and the only cost
     is anyio in `all` installs.

4. **Should `fetch_arrow_table()`'s async twin be pulled forward?**
   - What we know: `AsyncCursor.fetch_arrow_table` exists and is a coroutine
     [VERIFIED: `_async/_cursor.py:354`]; CONTEXT.md leaves this to discretion; Phase 49
     needs it.
   - Recommendation: yes — it is a two-line delegation, it needs no reader and therefore
     no close-ordering care, and it gives the streaming tests a cheap oracle to compare
     against.

5. **Should Semolina wrap `ConnectionBusyError`?**
   - What we know: poolhouse's message is already actionable — "an ADBC connection allows
     serialized but not concurrent access. Check out a separate connection per task."
     [VERIFIED: `_exceptions.py:57-61`]. It inherits `PoolhouseError` only, not
     `ValueError`.
   - What's unclear: whether Semolina users should ever see a poolhouse type.
   - Recommendation: let it propagate unwrapped for this phase, and document it. Because
     `aexecute()` checks out one connection per call, users can only reach it by
     deliberately sharing a cursor across tasks — the message already tells them not to.

## Sources

### Primary (HIGH confidence)

- `adbc-poolhouse` **1.6.1** wheel source, read in full this session:
  `adbc_poolhouse/__init__.py`, `_async/{__init__,_factory,_pool,_connection,_cursor,_reader,_cancel,_offload}.py`,
  `_exceptions.py`, `_duckdb_config.py`, `_base_config.py`, `_pool_factory.py`
- `adbc-poolhouse` **1.5.0 / 1.5.1 / 1.6.0** wheels, downloaded and diffed against 1.6.1
  to establish the `_resolve_tuning` regression boundary (Finding 1)
- Installed `pytest-adbc-replay` **1.1.1**: `plugin.py`, `_session.py`, `_cursor.py`,
  `_cassette_path.py`
- Installed `anyio` **4.13.0**: `pytest_plugin.py`, `dist-info/entry_points.txt`
- PyPI JSON API for `adbc-poolhouse`, `anyio`, `trio`, `pytest-adbc-replay`
- Executed `ruff check` with the proposed TID251 config on both ruff 0.15.x and v0.9.6
- Semolina repo, read this session: `pyproject.toml`, `src/semolina/{cursor,config,registry,__init__}.py`,
  `src/semolina/engines/base.py`, `tests/conftest.py`, `tests/integration/conftest.py`,
  `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `justfile`, `.planning/config.json`,
  cassette tree listing

### Secondary (MEDIUM confidence)

- anyio `docs/testing.md` via Context7 (`/agronholm/anyio`) — pytest plugin patterns
- ruff settings documentation for `lint.flake8-tidy-imports.banned-api` (the docs page
  did not state submodule behaviour, so I established that empirically instead)
- SQLAlchemy asyncio + pooling docs, as cited in CONTEXT.md for D-01/D-02/D-03 — carried
  forward, not independently re-fetched

### Tertiary (LOW confidence)

- None. Every load-bearing claim in this document is either quoted from source read this
  session or listed in the Assumptions Log.

## Metadata

**Confidence breakdown:**

- Standard stack: **HIGH** — versions confirmed against PyPI; the async API was read from
  the wheel rather than inferred; the version floor was established by diffing four
  releases
- Architecture: **HIGH** — every awaited call in the skeletons is a signature read from
  source; the close-ordering constraint is quoted from the guard implementation
- Pitfalls: **HIGH** — 1, 2, 3, 5, 6, 7 each rest on quoted source or an executed command;
  4 rests on read CI config
- Packaging: **HIGH** — extra names and `requires_dist` read from PyPI metadata; CI job
  shape read from `ci.yml`
- Test strategy: **MEDIUM-HIGH** — the mechanism is verified; timing reliability of the
  cancellation test (A3) and the cassette-copy match (A2) are the two items the plan's
  first tasks should confirm

**Research date:** 2026-08-01
**Valid until:** 2026-08-31 (30 days). `adbc-poolhouse` is moving fast — four releases
between 1.5.0 and 1.6.1 — so re-check the installed version's `_async/_factory.py` and
`_async/_connection.py` guard tiers if planning slips past that.
