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
"""

from __future__ import annotations

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
