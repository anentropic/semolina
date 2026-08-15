"""
The DTO codegen tracer: one query through every layer, on a live DuckDB engine.

Dotted path -> projection strip -> SQL build -> probe -> Arrow map -> alias binding ->
template render -> ``.into()`` round trip. The seams are what this module exists to check.
Every individual step is unit-tested elsewhere; what is not testable in pieces is whether a
generated class is one Semolina's own result surface accepts, which is the invariant Phase
50's RESEARCH names as Pitfall 2 — *Semolina never emits a class Semolina rejects*.

The generation half and the round-trip half are separate tests on purpose.
``data_fetch_guard`` fails any fetch from a non-metadata statement, which is exactly right
for the probe (threat T-50-04: neither probe route may pull a row) and exactly wrong for the
round trip, whose whole point is to pull rows through ``.into()``. Merging them would mean
dropping the guard from the probe, and the guard is the only thing that makes "the probe
fetches no data" a measurement rather than a claim.

The second half of the module is DTO-09: the same pipeline against a cursor made to refuse
``ExecuteSchema``, and the boundary between a driver that refuses (a capability gap with a
defined answer) and a probe that fails (a failure, to which a generated file is the wrong
response). :class:`TestARefusedExecuteSchemaStillGeneratesAClass` states precisely what that
proves and on which backend.
"""

from __future__ import annotations

import ast
import decimal
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import ModuleType

    from semolina.engines.base import Engine
    from semolina.query import _Query

QUERY_MODULE_NAME = "dto_tracer_queries"
"""Name of the throwaway user module the tracer resolves its query out of."""

QUERY_ATTRIBUTE = "value_by_region"
"""The module-level query attribute, chosen so its PascalCase form is worth asserting."""

QUERY_MODULE_SOURCE = f'''
"""A stand-in for a user's queries module, resolved by dotted path."""

from type_fidelity_probe import TypeFidelityView as View

{QUERY_ATTRIBUTE} = (
    View.query()
    .metrics(View.total_order_value, View.n_order_totals)
    .dimensions(View.region)
    .where(View.region == "US")
    .order_by(View.region)
    .limit(5)
)
'''
"""
The throwaway module's source.

Carries a filter, an ordering and a limit deliberately: D-02 says the DTO derives from the
projection alone, so a query with all three is a legal input and must produce the same class
as its unfiltered twin. ``US`` rather than the all-NULL ``CA`` group, so the round trip has a
non-NULL decimal to assert on.
"""


@pytest.fixture
def probe_engine() -> Generator[Engine]:
    """
    Yield the type-fidelity probe's in-memory DuckDB engine, closing its pool on teardown.

    Mirrors ``tests/unit/test_type_fidelity_duckdb.py``'s fixture of the same name. That
    module owns the record/replay contract this fixture inherits: the probe runs live and
    in-process, so no test using it may ever carry ``pytest.mark.adbc_cassette``.
    """
    from adbc_poolhouse import close_pool
    from type_fidelity_probe import make_probe_engine

    engine = make_probe_engine()
    yield engine
    close_pool(engine._pool)


@pytest.fixture
def resolved_query(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Query:
    """
    Write a throwaway queries module and resolve its query through the real dotted path.

    Exercises D-01 for real rather than handing the renderer a query built in-process:
    ``resolve_query`` appends the working directory to ``sys.path``, so the module has to be
    reachable from a chdir'd cwd and from nowhere else.

    ``sys.path`` is replaced with a copy before the call, so ``monkeypatch`` restores the
    original list object on teardown and the appended tmp directory cannot leak into another
    test's import resolution. The module is dropped from ``sys.modules`` for the same reason
    — a cached entry would make a second resolution silently reuse a deleted directory's
    module.

    Args:
        tmp_path: pytest's per-test temporary directory, standing in for a project root.
        monkeypatch: pytest's patching fixture.

    Returns:
        The resolved query, filter and ordering and limit intact.
    """
    from semolina.codegen.query_resolver import resolve_query

    (tmp_path / f"{QUERY_MODULE_NAME}.py").write_text(QUERY_MODULE_SOURCE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, QUERY_MODULE_NAME, raising=False)

    return resolve_query(f"{QUERY_MODULE_NAME}.{QUERY_ATTRIBUTE}")


def _import_generated(source: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """
    Write generated source to a file and import it the way a user would.

    ``exec``-ing the source into a bare dict is not equivalent and fails: Pydantic resolves
    a model's annotations through ``sys.modules[cls.__module__]``, and a class built in an
    anonymous namespace has ``__module__ == 'builtins'``, where ``decimal`` is not. The
    generated file is meant to be committed and imported, so importing it is also the
    faithful test.

    Args:
        source: The generated Python source.
        tmp_path: Where to write it.
        monkeypatch: Used to drop the module from ``sys.modules`` on teardown.

    Returns:
        The imported module.
    """
    import importlib.util

    name = "generated_dto_under_test"
    module_path = tmp_path / f"{name}.py"
    module_path.write_text(source)

    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _generate(engine: Engine, query: _Query) -> str:
    """
    Run the generation half of the pipeline and return the emitted source.

    Args:
        engine: The engine to probe against.
        query: The user's query, unstripped.

    Returns:
        Formatted Python source for one DTO class.
    """
    from semolina.codegen.dto_renderer import probe_query, render_and_format_dtos
    from semolina.codegen.query_resolver import class_name_for

    probed = probe_query(
        engine,
        query,
        class_name=class_name_for(QUERY_ATTRIBUTE),
        dotted_path=f"{QUERY_MODULE_NAME}.{QUERY_ATTRIBUTE}",
    )
    return render_and_format_dtos([probed], backend_label="duckdb")


def _refuse_execute_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Make every ADBC cursor answer ``NOT_IMPLEMENTED`` for ``ExecuteSchema``.

    The shape is copied from
    ``test_annotation_check.py::test_the_zero_row_fallback_route_runs_under_the_guard``
    rather than invented: patching the driver manager's own ``Cursor`` class is what keeps
    the rest of the cursor real, so the fallback SQL is compiled and executed by a live
    driver instead of answered by a stand-in.

    ``raising=True`` matters. If a future ``adbc_driver_manager`` renamed or dropped the
    method, a permissive patch would install an attribute nobody calls and every test below
    would quietly go back to exercising the primary route while still reading as a fallback
    test.

    Args:
        monkeypatch: pytest's patching fixture, or a ``monkeypatch.context()`` when the
            refusal has to be undone partway through a test.
    """
    import adbc_driver_manager  # pyright: ignore[reportMissingImports]
    import adbc_driver_manager.dbapi  # pyright: ignore[reportMissingImports]

    def refuse(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise adbc_driver_manager.NotSupportedError("ExecuteSchema not implemented")

    cursor_cls: Any = adbc_driver_manager.dbapi.Cursor
    monkeypatch.setattr(cursor_cls, "adbc_execute_schema", refuse, raising=True)


@pytest.fixture
def refused_execute_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Drive the probe down its zero-row fallback for the whole test.

    Args:
        monkeypatch: pytest's patching fixture; the refusal is undone at teardown.
    """
    _refuse_execute_schema(monkeypatch)


def _fields(source: str, class_name: str) -> dict[str, tuple[str, str]]:
    """
    Read a generated class's fields back out of the *parsed* source.

    Parsed rather than searched, because the claim these feed is that the two probe routes
    emit the same fields. Comparing source text would also compare the provenance header,
    which legitimately differs between the routes — that difference is the point of the
    route field — so the comparison has to be over the thing being claimed identical.

    Args:
        source: Generated Python source.
        class_name: The class to read.

    Returns:
        Field name -> (the annotation as ``ast.unparse`` re-renders it, the alias string the
        file really binds).

    Raises:
        AssertionError: If the source carries no such class, or a field is not the
            ``name: annotation = pydantic.Field(validation_alias=...)`` shape.
    """
    target: ast.ClassDef | None = None
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            target = node
    assert target is not None, f"No class {class_name!r} in:\n{source}"

    fields: dict[str, tuple[str, str]] = {}
    for stmt in target.body:
        if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
            continue
        call = stmt.value
        assert isinstance(call, ast.Call), ast.dump(stmt)
        for keyword in call.keywords:
            if keyword.arg != "validation_alias":
                continue
            assert isinstance(keyword.value, ast.Constant), ast.dump(keyword)
            alias: object = keyword.value.value
            assert isinstance(alias, str), ast.dump(keyword)
            fields[stmt.target.id] = (ast.unparse(stmt.annotation), alias)
    assert fields, f"No fields read from class {class_name!r} in:\n{source}"
    return fields


class TestTheTracer:
    """One query, every layer, against a live DuckDB semantic view."""

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_live_decimal_metric_is_annotated_decimal_not_float(
        self, probe_engine: Engine, resolved_query: _Query
    ) -> None:
        """
        The generated annotation for a ``decimal128(38, 2)`` metric is ``decimal.Decimal``.

        The roadmap's mandated end-to-end guard (D-06): a generated DTO must never annotate
        a decimal column ``float``. The check is on the *emitted source*, from a real probe
        of a real warehouse, not on a unit-tested mapping — the mapping already has its own
        tests, and what could still go wrong is a seam between them.

        ``float`` here would not merely be imprecise: Phase 49's ``.into()`` pre-check
        refuses ``decimal128`` into ``float`` on the fast path, so the generator would be
        emitting a class its own result surface rejects.
        """
        source = _generate(probe_engine, resolved_query)

        assert "total_order_value: decimal.Decimal | None" in source, source
        assert "float" not in source, source
        assert "import decimal" in source, source

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_class_is_named_after_the_query_attribute(
        self, probe_engine: Engine, resolved_query: _Query
    ) -> None:
        """The class name is the attribute's PascalCase form, per D-05."""
        source = _generate(probe_engine, resolved_query)

        assert "class ValueByRegion(pydantic.BaseModel):" in source, source

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_every_field_binds_to_a_result_column_by_name(
        self, probe_engine: Engine, resolved_query: _Query
    ) -> None:
        """
        Each projected field carries one plain-string alias naming a real result column.

        Names, never positions (threat T-50-06). DuckDB's ``semantic_view()`` returns
        dimensions before metrics while the projection declares metrics first, so a
        positional rule would bind ``total_order_value`` to ``region`` here and the test
        would still pass on a backend whose orders happened to agree.
        """
        source = _generate(probe_engine, resolved_query)

        assert 'validation_alias="total_order_value"' in source, source
        assert 'validation_alias="n_order_totals"' in source, source
        assert 'validation_alias="region"' in source, source
        assert "AliasChoices" not in source, source

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_metric_nullability_rule_reaches_the_emitted_source(
        self, probe_engine: Engine, resolved_query: _Query
    ) -> None:
        """
        Metrics carry ``| None``; the dimension does not.

        D-09 inheriting 47-DECISIONS Decision 2, applied through the shared
        ``metric_annotation`` helper. ``n_order_totals`` is a ``COUNT`` and is the
        documented over-approximation: it never returns NULL and is annotated as though it
        could, because the alternative is a heuristic that works on two backends of three.
        """
        source = _generate(probe_engine, resolved_query)

        assert "n_order_totals: int | None" in source, source
        assert "region: str = " in source, source
        assert "region: str | None" not in source, source

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_provenance_header_names_the_backend_and_the_probe_route(
        self, probe_engine: Engine, resolved_query: _Query
    ) -> None:
        """
        The header states which backend answered and which probe route produced the schema.

        The corrected D-04 and D-07: the generated class is pinned to one warehouse. Its
        aliases are that warehouse's spellings and its annotations reflect that warehouse's
        aggregation result typing, which is warehouse-defined. A file that did not say so
        would look portable and silently not be.
        """
        from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA

        source = _generate(probe_engine, resolved_query)

        assert "Backend: duckdb" in source, source
        assert f"probe route: {ROUTE_EXECUTE_SCHEMA}" in source, source
        assert "dialect: DuckDBDialect" in source, source
        assert f"{QUERY_MODULE_NAME}.{QUERY_ATTRIBUTE}" in source, source

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_header_cannot_name_a_backend_that_did_not_answer(
        self, probe_engine: Engine, resolved_query: _Query
    ) -> None:
        """
        Claiming a backend the dialect contradicts is refused, not written to the header.

        The provenance header is the generated file's evidence about where its aliases and
        annotations came from, and ``backend_label`` is the only part of it that is the
        caller's word rather than a measurement. A file headed ``Backend: snowflake`` over
        DuckDB-shaped aliases would read as evidence and be a lie the reader cannot catch,
        so the caller's label is checked against the dialect that actually built the SQL.
        """
        from semolina.codegen.dto_renderer import probe_query, render_dtos
        from semolina.codegen.query_resolver import class_name_for

        probed = probe_query(
            probe_engine,
            resolved_query,
            class_name=class_name_for(QUERY_ATTRIBUTE),
            dotted_path=f"{QUERY_MODULE_NAME}.{QUERY_ATTRIBUTE}",
        )

        with pytest.raises(ValueError, match=r"DuckDBDialect is 'duckdb'"):
            render_dtos([probed], backend_label="snowflake")

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_generated_module_does_not_import_semolina(
        self, probe_engine: Engine, resolved_query: _Query, tmp_path: Path
    ) -> None:
        """
        A generated DTO is a plain Pydantic model, importable without Semolina installed.

        Asserted twice, because the two halves fail differently: the source carries no
        ``semolina`` import at all, and importing the written file in a fresh interpreter
        leaves ``semolina`` absent from ``sys.modules``. The second catches a transitive
        pull-in that the first would miss.

        This is RESEARCH Assumption A3 made checkable, and it is what lets the generated
        file live in a service that has no Semolina dependency at runtime.
        """
        source = _generate(probe_engine, resolved_query)

        assert "import semolina" not in source, source
        assert "from semolina" not in source, source

        module_path = tmp_path / "generated_dto.py"
        module_path.write_text(source)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import importlib.util, sys\n"
                    "spec = importlib.util.spec_from_file_location('generated_dto', "
                    f"{str(module_path)!r})\n"
                    "assert spec is not None and spec.loader is not None\n"
                    "module = importlib.util.module_from_spec(spec)\n"
                    "sys.modules['generated_dto'] = module\n"
                    "spec.loader.exec_module(module)\n"
                    "assert 'semolina' not in sys.modules, sorted(sys.modules)\n"
                    "assert module.ValueByRegion.model_fields\n"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    def test_the_generated_class_round_trips_through_into(
        self,
        probe_engine: Engine,
        resolved_query: _Query,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Executing the ORIGINAL filtered query and calling ``.into()`` returns instances.

        No ``data_fetch_guard`` here, deliberately — this test pulls rows, which is the
        point. The guard covers the probe, in the tests above.

        The unstripped query is used on purpose: the DTO was generated from the projection
        alone (D-02), so it has to describe the filtered result too. And the assertion is on
        the *value's* type, not just on the annotation — a class that passed the pre-check
        and then handed back a ``float`` would satisfy every source-level assertion in this
        module.
        """
        import pydantic

        source = _generate(probe_engine, resolved_query)
        module = _import_generated(source, tmp_path, monkeypatch)

        dto: Any = module.ValueByRegion
        assert isinstance(dto, type) and issubclass(dto, pydantic.BaseModel)

        with probe_engine.execute(resolved_query) as cursor:
            rows = cursor.into(dto)

        assert rows, "the US group has seed rows, so the round trip must return instances"
        values = rows[0].model_dump()
        assert isinstance(values["total_order_value"], decimal.Decimal)
        assert isinstance(values["n_order_totals"], int)
        assert values["region"] == "US"


class TestResolvingTheDottedPath:
    """``resolve_query``'s error branches, which are the CLI's exit codes in plan 50-03."""

    def test_a_non_query_attribute_is_refused_by_the_type_it_actually_found(self) -> None:
        """
        Resolving a function rather than a query names ``function`` in the message.

        Naming the type found is what makes the error actionable: the common mistake is
        pointing at the query *builder method* or at the model class, and "not a query" on
        its own does not distinguish those.
        """
        from semolina.codegen.query_resolver import resolve_query

        with pytest.raises(ValueError, match=r"resolved to a function, not a query"):
            resolve_query("semolina.codegen.probe.probe_schema")

    def test_a_missing_module_names_the_path(self) -> None:
        """An unimportable module is refused with the module path in the message."""
        from semolina.codegen.query_resolver import resolve_query

        with pytest.raises(ValueError, match=r"Cannot import module 'no_such_module_here'"):
            resolve_query("no_such_module_here.some_query")

    def test_a_missing_attribute_names_the_attribute(self) -> None:
        """A module without the named attribute is refused, naming the attribute."""
        from semolina.codegen.query_resolver import resolve_query

        with pytest.raises(ValueError, match=r"has no attribute 'no_such_query'"):
            resolve_query("semolina.codegen.probe.no_such_query")

    def test_a_bare_name_with_no_module_part_is_refused(self) -> None:
        """A path carrying no dot names no module, so there is nothing to import."""
        from semolina.codegen.query_resolver import resolve_query

        with pytest.raises(ValueError, match=r"expected a dotted path"):
            resolve_query("revenue_by_region")

    def test_the_working_directory_is_appended_to_sys_path_not_prepended(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Cwd goes on the END of ``sys.path`` (threat T-50-03).

        Prepending would let a file in the working directory shadow an installed
        distribution of the same name, for the resolved module and for everything it then
        imports. The position is the mitigation, so the position is what is asserted — and
        it is asserted by index rather than by membership, because membership passes either
        way.
        """
        from semolina.codegen.query_resolver import resolve_query

        (tmp_path / f"{QUERY_MODULE_NAME}.py").write_text(QUERY_MODULE_SOURCE)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "path", list(sys.path))
        monkeypatch.delitem(sys.modules, QUERY_MODULE_NAME, raising=False)

        resolve_query(f"{QUERY_MODULE_NAME}.{QUERY_ATTRIBUTE}")

        cwd = str(Path.cwd())
        assert sys.path[-1] == cwd
        assert sys.path[0] != cwd


class TestARefusedExecuteSchemaStillGeneratesAClass:
    r"""
    DTO-09: refusing ``ExecuteSchema`` is a capability gap with a defined answer, not a failure.

    **What is proven here, and what is not.**

    *Proven:* the fallback **branch**, on a live DuckDB cursor made to refuse. The zero-row
    wrapper is compiled and executed by a real driver, the schema comes back off
    ``reader.schema``, and the class built from it is field-for-field identical to the one
    the primary route produces for the same query. That is the strongest statement this
    repository can make without a warehouse in the room.

    *Not proven:* that DTO-09 holds on **Databricks**, which is the backend that will
    actually take this branch. Its Foundry ADBC driver defines no ``ExecuteSchema`` at
    ``go/v0.1.2`` or ``go/v0.1.3`` (byte-identical files; re-read in Phase 48, plan 48-04),
    so the zero-row wrapper is its only route to a result schema — and nobody has run it.
    Whether the Databricks metric-view planner accepts
    ``SELECT * FROM (<MEASURE(...) ... GROUP BY ALL>) WHERE 1=0`` is unmeasured, and if it
    does not, DTO codegen has no working route on that backend at all.

    ``pytest-adbc-replay`` **structurally cannot settle it.** It serves
    ``adbc_execute_schema`` from the recorded result table regardless of what the real
    driver does, so a replayed Databricks probe returns a schema whatever the driver would
    have answered — a green cassette test here would look like evidence and be none. None is
    added, deliberately. Only a live workspace closes it:
    ``.planning/todos/pending/2026-08-12-verify-databricks-zero-row-fallback.md``.

    Also note what the DuckDB engine cannot distinguish on its own: its metric and dimension
    result columns are both the bare field name, so a wrong candidate list would still
    resolve here. The per-backend spellings — ``AGG("REVENUE")``, ``measure(revenue)`` — are
    pinned offline in ``test_dto_renderer.py`` against this repo's own recordings, which is
    strictly weaker than a live probe and strictly stronger than re-deriving them.
    """

    @pytest.mark.usefixtures("data_fetch_guard", "refused_execute_schema")
    def test_a_refused_execute_schema_still_yields_a_class(
        self, probe_engine: Engine, resolved_query: _Query
    ) -> None:
        """
        Codegen degrades to the fallback route rather than failing hard.

        This is DTO-09's own wording — *a working fallback rather than a hard failure* — and
        it is the weakest of the four claims in this class, so it is asserted first and on
        its own. A driver that refuses ``ExecuteSchema`` must not cost the user their DTO.
        """
        source = _generate(probe_engine, resolved_query)

        assert "class ValueByRegion(pydantic.BaseModel):" in source, source
        assert _fields(source, "ValueByRegion"), source

    @pytest.mark.usefixtures("data_fetch_guard", "refused_execute_schema")
    def test_the_generated_file_reports_the_zero_row_route(
        self, probe_engine: Engine, resolved_query: _Query
    ) -> None:
        """
        The provenance header says the schema came from the fallback, not the primary route.

        Read from :mod:`semolina.codegen.probe`'s own constants rather than written out as
        strings, so renaming a route label fails this test instead of silently leaving it
        asserting a value nothing emits any more (threat T-50-07).
        """
        from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA, ROUTE_ZERO_ROW

        source = _generate(probe_engine, resolved_query)

        assert f"probe route: {ROUTE_ZERO_ROW}" in source, source
        assert f"probe route: {ROUTE_EXECUTE_SCHEMA}" not in source, source

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_primary_route_reports_execute_schema_on_the_same_engine(
        self, probe_engine: Engine, resolved_query: _Query
    ) -> None:
        """
        Without the refusal, the same engine reports the primary route.

        The companion to the test above, and the reason either is worth anything: a route
        field that never varies would read correctly in a fallback test while being a
        constant. Same engine, same query, one monkeypatch of difference.
        """
        from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA, ROUTE_ZERO_ROW

        source = _generate(probe_engine, resolved_query)

        assert f"probe route: {ROUTE_EXECUTE_SCHEMA}" in source, source
        assert f"probe route: {ROUTE_ZERO_ROW}" not in source, source

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_both_routes_produce_the_same_annotations_and_aliases(
        self, probe_engine: Engine, resolved_query: _Query, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The two routes disagree about nothing except which route they were.

        The route is a *source* for the same schema, so a user whose driver refuses
        ``ExecuteSchema`` must get the same class as a user whose driver does not — a
        fallback that quietly widened a type or bound a different column would be worse than
        a hard failure, because it would ship.

        Both sources are generated inside this one test rather than compared across tests,
        and the route assertions guard against the comparison silently becoming
        primary-versus-primary if the refusal ever stops taking effect.
        """
        from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA, ROUTE_ZERO_ROW

        primary = _generate(probe_engine, resolved_query)
        with monkeypatch.context() as refusing:
            _refuse_execute_schema(refusing)
            fallback = _generate(probe_engine, resolved_query)

        assert f"probe route: {ROUTE_EXECUTE_SCHEMA}" in primary, primary
        assert f"probe route: {ROUTE_ZERO_ROW}" in fallback, fallback
        assert _fields(fallback, "ValueByRegion") == _fields(primary, "ValueByRegion")

    @pytest.mark.usefixtures("refused_execute_schema")
    def test_the_fallback_class_round_trips_through_into(
        self,
        probe_engine: Engine,
        resolved_query: _Query,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        A class generated on the fallback route is one Semolina's own result surface accepts.

        No ``data_fetch_guard``, for the reason the tracer's round trip carries none: this
        test pulls rows on purpose. The invariant is RESEARCH Pitfall 2 — *Semolina never
        emits a class Semolina rejects* — and it has to hold on both routes, because a
        Databricks user only ever gets this one.

        ``.into()`` never calls ``adbc_execute_schema``, so the refusal that forced the
        fallback during generation leaves the execution path untouched.
        """
        source = _generate(probe_engine, resolved_query)
        module = _import_generated(source, tmp_path, monkeypatch)

        dto: Any = module.ValueByRegion

        with probe_engine.execute(resolved_query) as cursor:
            rows = cursor.into(dto)

        assert rows, "the US group has seed rows, so the round trip must return instances"
        values = rows[0].model_dump()
        assert isinstance(values["total_order_value"], decimal.Decimal)
        assert values["region"] == "US"
