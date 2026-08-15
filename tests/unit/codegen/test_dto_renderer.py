"""
Pin D-02: the DTO derives from the query's projection and nothing else.

Two invariants, and they are separate claims. The first is about SQL — a stripped query
binds no parameters, on every builder — and the second is about output — a filtered query and
its unfiltered twin render byte-identical source. The first is what keeps Snowflake's primary
probe route reachable; the second is the user-facing rule D-02 actually states.

Both are stated as tests rather than as reasoning because both are properties of code that
lives elsewhere: ``all_params.extend(where_params)`` being the only parameter source in
either builder is true today and nothing else would notice if it stopped being true.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from semolina.engines.base import Engine
    from semolina.engines.sql import Dialect
    from semolina.query import _Query

PARAMETER_BINDING_DIALECTS = ("SnowflakeDialect", "DuckDBDialect")
"""
The dialects whose builders emit placeholders and a parameter list.

``DatabricksDialect`` sets ``supports_parameterized_queries = False``, so its builder renders
every value as a SQL literal and returns ``[]`` for *any* query, stripped or not. It is
excluded from the vacuity guard for that reason and only that reason — the D-02 invariant
still holds there, it just holds for a second, independent reason and so cannot distinguish a
working strip from a broken one.
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


def _dialect(name: str) -> Dialect:
    """
    Build a dialect by class name.

    Args:
        name: ``'SnowflakeDialect'``, ``'DatabricksDialect'`` or ``'DuckDBDialect'``.

    Returns:
        A fresh instance, so a parametrised case cannot inherit another's state.
    """
    from semolina.engines import sql

    dialect_cls: type[Dialect] = getattr(sql, name)
    return dialect_cls()


def _filtered_query() -> _Query:
    """
    Build a query carrying a metric, a dimension, a filter, an ordering and a limit.

    Returns:
        The query, unstripped.
    """
    from type_fidelity_probe import TypeFidelityView as View

    return (
        View.query()
        .metrics(View.total_order_value, View.n_order_totals)
        .dimensions(View.region)
        .where(View.region == "US")
        .order_by(View.region)
        .limit(5)
    )


def _plain_query() -> _Query:
    """
    Build the unfiltered twin of :func:`_filtered_query` — same projection, nothing else.

    Returns:
        The query.
    """
    from type_fidelity_probe import TypeFidelityView as View

    return View.query().metrics(View.total_order_value, View.n_order_totals).dimensions(View.region)


class TestTheProbedQueryIsParamFree:
    """
    A projection-only query binds no parameters, so the primary probe route stays reachable.

    Snowflake refuses ``ExecuteSchema`` for a query carrying a bound parameter. DTO codegen
    depends on the primary route on every backend, and what guarantees it is not the probe —
    it is that :func:`~semolina.codegen.query_resolver.projection_only` removes the only
    clause that binds anything. That is a property of two SQL builders neither of which knows
    this module exists, which is exactly why it is asserted rather than reasoned about.
    """

    @pytest.mark.parametrize(
        "dialect_name", ["SnowflakeDialect", "DatabricksDialect", "DuckDBDialect"]
    )
    def test_a_stripped_query_is_param_free(self, dialect_name: str) -> None:
        """
        Every builder returns an empty parameter list for a projection-only query.

        Parametrised per dialect rather than looped, so a future builder change fails on the
        backend that regressed instead of in one undifferentiated lump.
        """
        from semolina.codegen.query_resolver import projection_only

        builder = _dialect(dialect_name).create_builder()
        _sql, params = builder.build_select_with_params(projection_only(_filtered_query()))

        assert params == []

    @pytest.mark.parametrize("dialect_name", PARAMETER_BINDING_DIALECTS)
    def test_the_unstripped_query_does_bind_parameters(self, dialect_name: str) -> None:
        """
        The vacuity guard: the same query, unstripped, binds a parameter.

        Without this, ``params == []`` above would keep passing against a builder that had
        stopped binding anything at all — and a test that cannot fail proves nothing. Only
        the parameter-binding dialects can carry the guard; see
        :data:`PARAMETER_BINDING_DIALECTS`.
        """
        builder = _dialect(dialect_name).create_builder()
        _sql, params = builder.build_select_with_params(_filtered_query())

        assert params == ["US"]

    @pytest.mark.parametrize(
        "dialect_name", ["SnowflakeDialect", "DatabricksDialect", "DuckDBDialect"]
    )
    def test_the_stripped_sql_carries_no_filter_ordering_or_limit(self, dialect_name: str) -> None:
        """
        The three stripped clauses are gone from the SQL, not merely unparameterised.

        Databricks inlines its values, so an empty parameter list alone would not tell you
        the ``WHERE`` had been removed there — it would look identical whether the strip
        worked or not.
        """
        from semolina.codegen.query_resolver import projection_only

        builder = _dialect(dialect_name).create_builder()
        sql, _params = builder.build_select_with_params(projection_only(_filtered_query()))

        assert "WHERE" not in sql.upper()
        assert "ORDER BY" not in sql.upper()
        assert "LIMIT" not in sql.upper()
        assert "'US'" not in sql

    def test_stripping_preserves_the_bound_model(self) -> None:
        """
        ``_replace`` keeps ``_model``, which ``dataclasses.replace`` would drop.

        ``_model`` is declared ``init=False``, so plain ``replace`` returns a query that no
        longer knows which model it came from. Nothing downstream of the strip would fail
        loudly on that — the builder reads field ``owner`` instead — so the difference would
        surface much later, somewhere else.
        """
        from semolina.codegen.query_resolver import projection_only

        query = _filtered_query()
        stripped = projection_only(query)

        assert stripped._model is query._model
        assert stripped._model is not None
        assert stripped._metrics == query._metrics
        assert stripped._dimensions == query._dimensions


class TestTheDtoDerivesFromTheProjectionAlone:
    """D-02 stated as one sentence and checked as one assertion."""

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_filtered_query_and_its_unfiltered_twin_render_identical_source(
        self, probe_engine: Engine
    ) -> None:
        """
        Two queries over one projection produce byte-identical generated source.

        Probed separately against the live DuckDB view, so this compares two real round
        trips through the builder and the driver rather than two calls to the same cached
        schema. A filter changes which rows come back, not what shape they are — and the
        user-visible consequence is that a filtered query is a legal input to DTO codegen
        and is not a different DTO.

        The mechanism is asserted alongside the outcome, because the outcome alone is a weak
        guard here: the DTO's field list is read off the query object and its annotations off
        column types, neither of which a ``WHERE`` perturbs, so equal source would survive a
        ``projection_only`` that did nothing. Asserting that the two *probed statements* are
        one statement — and that the two unstripped statements are not — is what makes this
        test able to fail.
        """
        from semolina.codegen.dto_renderer import probe_query, render_and_format_dtos
        from semolina.codegen.query_resolver import projection_only

        builder = probe_engine.dialect.create_builder()
        assert builder.build_select_with_params(
            projection_only(_filtered_query())
        ) == builder.build_select_with_params(projection_only(_plain_query()))
        assert builder.build_select_with_params(
            _filtered_query()
        ) != builder.build_select_with_params(_plain_query())

        sources: list[str] = []
        for query in (_filtered_query(), _plain_query()):
            probed = probe_query(
                probe_engine,
                query,
                class_name="ValueByRegion",
                dotted_path="myapp.queries.value_by_region",
            )
            sources.append(render_and_format_dtos([probed], backend_label="duckdb"))

        assert sources[0] == sources[1]
        assert "total_order_value: decimal.Decimal | None" in sources[0], sources[0]
