"""
Pin the DTO renderer's four rules, offline: alias, nullability, unmapped types, imports.

The tracer in ``test_dto_codegen_e2e.py`` proves the pipeline end to end on a live DuckDB
engine — and DuckDB is the one backend where a metric and a dimension both come back under
the bare field name, so a wrong candidate list would still resolve there. This module is
where the other two backends are checked, against a synthetic ``pyarrow`` schema built from
the column names this repo has actually recorded rather than against a re-derivation of the
dialect's own spelling rules. Every spelling in
:data:`MEASURED_RESULT_COLUMNS` is derivable with no I/O, so no test here opens a connection.

Four claims, each a property of code that lives elsewhere:

* **D-02** — a stripped query binds no parameters on every builder, and a filtered query and
  its unfiltered twin render byte-identical source. ``all_params.extend(where_params)`` being
  the only parameter source in either builder is true today and nothing else would notice if
  it stopped being true.
* **The corrected D-04** — one per-backend alias, and it is the spelling that backend really
  returns.
* **D-09** — every metric annotation carries ``| None`` and no dimension or fact annotation
  does.
* **D-06** — an Arrow type with no clean Python equivalent renders ``Any`` plus a comment
  naming the type, never a guess.

Generated source is inspected by parsing it with :mod:`ast` wherever the claim is about
Python rather than about text. A substring search would pass just as happily on source that
does not parse, and the whole point of the escaping rules is that a warehouse-shaped alias
stays inside its own string literal in a file the documented workflow tells users to import.
"""

from __future__ import annotations

import ast
import decimal
import sys
import types
from typing import TYPE_CHECKING

import pyarrow
import pydantic
import pytest

from semolina import Dimension, Fact, Metric, SemanticView
from semolina.codegen.dto_renderer import ProbedQuery, render_dtos
from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA, ROUTE_ZERO_ROW

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from semolina.engines.base import Engine
    from semolina.engines.sql import Dialect
    from semolina.query import _Query

MEASURED_RESULT_COLUMNS: dict[str, dict[str, str]] = {
    "SnowflakeDialect": {"revenue": 'AGG("REVENUE")', "country": "COUNTRY"},
    "DatabricksDialect": {"revenue": "measure(revenue)", "country": "country"},
    "DuckDBDialect": {"revenue": "revenue", "country": "country"},
}
"""
Dialect -> field name -> the result column that backend returns for it.

The measured table from ``50-RESEARCH.md`` § "The result-column spelling table (measured,
not derived)", quoted rather than recomputed. Per-cell provenance:

* **Snowflake** — ``tests/type_fidelity_probe.py``'s ``SNOWFLAKE_DERIVED_METADATA``, whose
  keys are verbatim ``'AGG("REVENUE")'`` and ``'COUNTRY'``.
* **Databricks** — ``DATABRICKS_FIELD_SOURCES`` in the same module, recorded as
  ``{"measure(revenue)": "revenue", "country": "country"}`` with the note that Databricks
  returns the metric column lower-cased and unquoted rather than as the ``MEASURE(`revenue`)``
  it was sent. One cassette, one metric name that needed no quoting: what Databricks answers
  for a name requiring backticks is unmeasured (RESEARCH assumption A1) and is not widened
  here.
* **DuckDB** — a live probe whose schema field names came back bare and unquoted.

Feeding these into a synthetic schema is what makes the assertions below test the *picker*.
Asserting the candidate list itself is ``test_annotation_check.py``'s job, and a copy of it
here would keep passing against a picker that had stopped walking the list.
"""

BACKEND_LABELS: dict[str, str] = {
    "SnowflakeDialect": "snowflake",
    "DatabricksDialect": "databricks",
    "DuckDBDialect": "duckdb",
}
"""
Dialect class name -> the backend label its provenance header must claim.

``render_dtos`` refuses a label that contradicts the dialect that answered, so every render
below has to pass the matching one — which is the check working, not a test detail.
"""

INJECTING_CLASS_NAME = (
    "X:\n    pass\n\nimport os\nos.system('echo INJECTED')\n\nclass Bar:\n    pass  #"
)
"""
The Phase 50 review's proof of concept, verbatim: a class name that is a whole module.

Written into ``class <name>(pydantic.BaseModel):`` it closes the class statement, adds a
top-level ``import os`` and an ``os.system(...)`` call, and reopens a class whose trailing
``#`` swallows the rest of the template's line. Quoted rather than paraphrased because a
friendlier payload would keep passing against a fix that merely rejected whitespace.
"""

NON_IDENTIFIER_CLASS_NAMES = [
    pytest.param(INJECTING_CLASS_NAME, id="statement-injection"),
    pytest.param("X;__import__('os')", id="no-whitespace"),
    pytest.param("class", id="keyword"),
    pytest.param("", id="empty"),
]
"""
The four shapes a refused class name comes in, each pinning a different half of the rule.

``statement-injection`` is the threat itself; ``no-whitespace`` is the same threat carrying
no space; ``keyword`` is the case ``str.isidentifier`` gets wrong on its own, answering
``True`` for ``'class'``; ``empty`` is what the derived path produces for a dotted path with
no attribute part.
"""


class AliasSales(SemanticView, view="dto_alias_sales"):
    """
    A three-field model whose names are the ones ``50-RESEARCH.md`` measured.

    ``revenue`` and ``country`` are the table's own two rows. ``unit_price`` is a ``Fact``,
    carried so metric nullability can be checked against a *third* role rather than only
    against its opposite: D-09 applies to metrics, and a rule that happened to key on "not a
    dimension" would pass a two-role test.
    """

    revenue = Metric[int]()
    country = Dimension[str]()
    unit_price = Fact[float]()


class UnderscoreSales(SemanticView, view="dto_underscore_sales"):
    """
    A model carrying a field name pydantic cannot accept, which codegen has to refuse.

    A warehouse column really can be called ``_id``, and nothing on the model side objects:
    the descriptor validates identifiers and keywords, and ``_id`` is both a legal
    identifier and not a keyword.
    """

    _id = Dimension[str]()
    revenue = Metric[int]()


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
        A fresh instance, so a parametrized case cannot inherit another's state.
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


def _probed(
    dialect_name: str,
    query: _Query,
    columns: Sequence[tuple[str, pyarrow.DataType]],
    *,
    class_name: str = "RevenueByCountry",
    origin: str = "myapp.queries.revenue_by_country",
    route: str = ROUTE_EXECUTE_SCHEMA,
) -> ProbedQuery:
    """
    Build a ``ProbedQuery`` from a hand-written schema, with no warehouse in the loop.

    Everything the renderer reads is either the query object or the dialect, and every
    dialect method it calls (``quote_identifier``, ``wrap_metric``,
    ``metric_result_column_name``, ``normalize_identifier``) is pure. So a probed schema is
    the only input that normally needs a connection, and supplying it directly is what lets
    the Snowflake and Databricks spellings be checked in a unit test.

    Args:
        dialect_name: ``'SnowflakeDialect'``, ``'DatabricksDialect'`` or ``'DuckDBDialect'``.
        query: The query whose projection becomes the DTO's fields.
        columns: ``(name, type)`` pairs, in the order the warehouse would return them.
        class_name: The generated class's name.
        origin: The dotted path the header and class docstring name.
        route: The probe route the header reports.

    Returns:
        The record ``render_dtos`` takes.
    """
    schema = pyarrow.schema([pyarrow.field(name, dtype) for name, dtype in columns])
    return ProbedQuery(
        class_name=class_name,
        origin=origin,
        query=query,
        dialect=_dialect(dialect_name),
        schema=schema,
        route=route,
    )


def _measured_columns(dialect_name: str) -> list[tuple[str, pyarrow.DataType]]:
    """
    Build the result schema the named backend really returns for :class:`AliasSales`.

    Args:
        dialect_name: The dialect class name.

    Returns:
        The metric column as a ``decimal128`` and the dimension column as a string, under
        the spellings :data:`MEASURED_RESULT_COLUMNS` records.
    """
    names = MEASURED_RESULT_COLUMNS[dialect_name]
    return [
        (names["revenue"], pyarrow.decimal128(38, 2)),
        (names["country"], pyarrow.string()),
    ]


def _class_def(source: str, class_name: str) -> ast.ClassDef:
    """
    Find one class in generated source, by parsing it rather than by reading it.

    Args:
        source: Generated Python source.
        class_name: The class to find.

    Returns:
        Its ``ast.ClassDef`` node.

    Raises:
        AssertionError: If the source carries no such class — which also fails the test
            usefully when the source parses but renders nothing.
    """
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise AssertionError(f"No class {class_name!r} in:\n{source}")


def _annotations(source: str, class_name: str) -> dict[str, str]:
    """
    Read a generated class's field annotations back out of the parsed source.

    Args:
        source: Generated Python source.
        class_name: The class to read.

    Returns:
        Field name -> the annotation as ``ast.unparse`` re-renders it, so ``| None`` is
        compared as a parsed union rather than as trailing text.
    """
    return {
        stmt.target.id: ast.unparse(stmt.annotation)
        for stmt in _class_def(source, class_name).body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }


def _aliases(source: str, class_name: str) -> dict[str, str]:
    """
    Read a generated class's ``validation_alias`` values back out of the parsed source.

    Reading the *parsed* value rather than the source text is what makes the escaping cases
    meaningful: a literal that closed itself early would either fail to parse or come back
    as a different string, and both fail here.

    Args:
        source: Generated Python source.
        class_name: The class to read.

    Returns:
        Field name -> the alias string the generated file actually binds.
    """
    aliases: dict[str, str] = {}
    for stmt in _class_def(source, class_name).body:
        if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
            continue
        call = stmt.value
        assert isinstance(call, ast.Call), ast.dump(stmt)
        for keyword in call.keywords:
            if keyword.arg == "validation_alias":
                assert isinstance(keyword.value, ast.Constant), ast.dump(keyword)
                value: object = keyword.value.value
                assert isinstance(value, str), ast.dump(keyword)
                aliases[stmt.target.id] = value
    return aliases


def _import_statements(source: str) -> list[str]:
    """
    List a generated module's top-level import statements, in emission order.

    Args:
        source: Generated Python source.

    Returns:
        Each import re-rendered by ``ast.unparse``, so ``import decimal`` is compared as a
        statement rather than as a substring that a docstring could also satisfy.
    """
    return [
        ast.unparse(node)
        for node in ast.parse(source).body
        if isinstance(node, ast.Import | ast.ImportFrom)
    ]


def _imported_modules(source: str) -> set[str]:
    """
    Name every module a generated file imports, however it imports it.

    Args:
        source: Generated Python source.

    Returns:
        Module names from both ``import x`` and ``from x import y`` forms.
    """
    modules: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _comment_above(source: str, field_name: str) -> str:
    """
    Read the comment line immediately above a field in generated source.

    Comments are the one thing :mod:`ast` discards, so this reads text — deliberately, and
    only for the claim that is about text: whether the comment occupies exactly one physical
    line.

    Args:
        source: Generated Python source.
        field_name: The field whose comment to read.

    Returns:
        The stripped comment line, or the empty string when the line above is not a comment.

    Raises:
        AssertionError: If the source declares no such field.
    """
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith(f"{field_name}:"):
            previous = lines[index - 1].strip()
            return previous if previous.startswith("#") else ""
    raise AssertionError(f"No field {field_name!r} in:\n{source}")


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

        Parametrized per dialect rather than looped, so a future builder change fails on the
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
        The three stripped clauses are gone from the SQL, not merely unparameterized.

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
                origin="myapp.queries.value_by_region",
            )
            sources.append(render_and_format_dtos([probed], backend_label="duckdb"))

        assert sources[0] == sources[1]
        assert "total_order_value: decimal.Decimal | None" in sources[0], sources[0]


def _alias_sales_query() -> _Query:
    """
    Build the one-metric, one-dimension query the measured table describes.

    Returns:
        The query.
    """
    return AliasSales.query().metrics(AliasSales.revenue).dimensions(AliasSales.country)


class TestTheAliasIsTheSpellingTheBackendReturns:
    """
    The corrected D-04, one case per measured cell.

    A generated DTO is pinned to the backend it was probed against, so its aliases have to be
    that backend's spellings and no other's. The three backends genuinely disagree — the same
    metric comes back as ``AGG("REVENUE")``, ``measure(revenue)`` and ``revenue`` — and the
    portable alternative does not exist: arrowmodel raises ``NotImplementedError`` for the
    multi-alias Pydantic form before either conversion path is reachable (RESEARCH R-01).

    Each case feeds the renderer a schema carrying that backend's recorded column names and
    asserts the alias the generated file binds. What that tests is the *picker* — whether
    ``_alias_for`` walks the candidate list and stops at the name the warehouse really
    returned. Asserting the candidate list is a different test and already exists in
    ``test_annotation_check.py``; repeating it here would pass against a broken picker.
    """

    @pytest.mark.parametrize(
        ("dialect_name", "field_name"),
        [
            pytest.param("SnowflakeDialect", "revenue", id="snowflake-metric"),
            pytest.param("SnowflakeDialect", "country", id="snowflake-dimension"),
            pytest.param("DatabricksDialect", "revenue", id="databricks-metric"),
            pytest.param("DatabricksDialect", "country", id="databricks-dimension"),
            pytest.param("DuckDBDialect", "revenue", id="duckdb-metric"),
            pytest.param("DuckDBDialect", "country", id="duckdb-dimension"),
        ],
    )
    def test_the_generated_alias_is_the_measured_result_column(
        self, dialect_name: str, field_name: str
    ) -> None:
        """
        The emitted alias equals the column name this repo recorded for that backend.

        See :data:`MEASURED_RESULT_COLUMNS` for each cell's provenance. The schema always
        carries *both* columns, because a real result does — a per-field schema would let a
        picker that returned the schema's only name pass six times over.
        """
        probed = _probed(dialect_name, _alias_sales_query(), _measured_columns(dialect_name))

        source = render_dtos([probed], backend_label=BACKEND_LABELS[dialect_name])

        assert _aliases(source, "RevenueByCountry") == {
            "revenue": MEASURED_RESULT_COLUMNS[dialect_name]["revenue"],
            "country": MEASURED_RESULT_COLUMNS[dialect_name]["country"],
        }

    def test_the_snowflake_metric_alias_keeps_its_quotes_inside_a_single_quoted_literal(
        self,
    ) -> None:
        """
        ``AGG("REVENUE")`` is emitted single-quoted, so its own double quotes survive.

        This is ``_python_str_literal``'s swap-back branch reached by the most ordinary input
        there is: Snowflake's canonical metric result column carries a double quote in the
        middle of the one string this template writes most of. The generated file's house
        style is double quotes and ``repr`` is allowed to overrule it exactly here.
        """
        probed = _probed(
            "SnowflakeDialect", _alias_sales_query(), _measured_columns("SnowflakeDialect")
        )

        source = render_dtos([probed], backend_label="snowflake")

        assert "validation_alias='AGG(\"REVENUE\")'" in source, source

    def test_the_databricks_metric_alias_is_emitted_double_quoted(self) -> None:
        """
        ``measure(revenue)`` carries no quote, so it keeps the file's double-quoted style.

        The companion to the Snowflake case: the swap-back is conditional, and a rule that
        emitted single quotes for everything would pass that test and fail this one.
        """
        probed = _probed(
            "DatabricksDialect", _alias_sales_query(), _measured_columns("DatabricksDialect")
        )

        source = render_dtos([probed], backend_label="databricks")

        assert 'validation_alias="measure(revenue)"' in source, source


def _load_generated(source: str, class_name: str) -> type[pydantic.BaseModel]:
    """
    Execute rendered DTO source as a real module and hand back one of its model classes.

    Pydantic resolves a model's annotations through the defining module, so ``exec`` into a
    bare dict leaves ``decimal`` unresolvable and every model half-built. Registering a real
    module is what makes the generated file behave the way it does in a user's project.

    Args:
        source: The rendered DTO module source.
        class_name: The generated class to return.

    Returns:
        The generated model class.
    """
    module = types.ModuleType("_generated_dto_under_test")
    sys.modules[module.__name__] = module
    try:
        exec(compile(source, module.__name__, "exec"), module.__dict__)  # noqa: S102
    finally:
        sys.modules.pop(module.__name__, None)
    generated = module.__dict__[class_name]
    assert isinstance(generated, type)
    assert issubclass(generated, pydantic.BaseModel)
    return generated


class TestTheGeneratedDtoAcceptsItsOwnFieldNames:
    """
    ALIAS-02 accept-by-name, applied to the classes codegen writes rather than hand-written ones.

    :func:`semolina.dto.resolve_column_keys` documents accept-by-name as a supported mode, and
    :ref:`howto-typed-results` tells anyone hand-writing a DTO to set ``populate_by_name``. A
    generated DTO binds ``validation_alias`` on every field, which *replaces* the field name
    during validation unless that config is set -- so without it the generated class is the one
    kind of DTO that cannot be built from its own field names.

    That gap is invisible on DuckDB, where the alias equals the field name, and the docs walk
    the reader straight into it: the testing tutorial constructs ``RevenueByCountry(country=...,
    revenue=...)`` against DuckDB, and the codegen tutorial then tells them to regenerate the
    same class against their real warehouse. Both backends here spell at least one column
    differently from its field, so the alias and the field name cannot be confused.
    """

    @pytest.mark.parametrize(
        "dialect_name",
        [
            pytest.param("SnowflakeDialect", id="snowflake"),
            pytest.param("DatabricksDialect", id="databricks"),
        ],
    )
    def test_the_generated_dto_can_be_constructed_from_its_field_names(
        self, dialect_name: str
    ) -> None:
        """
        The rendered class is executed and instantiated by field name, not merely inspected.

        Reading ``model_config`` off the source would pass against a class that sets the flag
        and still rejects the call, so the assertion is the construction itself.
        """
        probed = _probed(dialect_name, _alias_sales_query(), _measured_columns(dialect_name))

        source = render_dtos([probed], backend_label=BACKEND_LABELS[dialect_name])
        dto_class = _load_generated(source, "RevenueByCountry")

        instance = dto_class(country="CA", revenue=decimal.Decimal("2000"))

        assert instance.model_dump() == {"country": "CA", "revenue": decimal.Decimal("2000")}

    def test_the_generated_dto_still_accepts_the_warehouse_alias(self) -> None:
        """
        Accept-by-name is additive: the alias path is what reads a real result and must survive.

        Pinned separately because the obvious wrong fix -- dropping ``validation_alias`` so the
        field names line up -- would satisfy the test above and break every actual conversion.
        """
        probed = _probed(
            "SnowflakeDialect", _alias_sales_query(), _measured_columns("SnowflakeDialect")
        )

        source = render_dtos([probed], backend_label="snowflake")
        dto_class = _load_generated(source, "RevenueByCountry")

        instance = dto_class(**{"COUNTRY": "CA", 'AGG("REVENUE")': decimal.Decimal("2000")})

        assert instance.model_dump() == {"country": "CA", "revenue": decimal.Decimal("2000")}


class TestOnlyMetricsAreNullable:
    """
    D-09 as a role-scoped rule, read back off the parsed annotations.

    47-DECISIONS Decision 2: metric annotations are uniformly ``T | None``, COUNT included as
    a documented over-approximation. Nothing else is decorated — a dimension is a group key
    and a fact is a raw column, and widening either would make every generated DTO claim a
    nullability the warehouse never reported.
    """

    def test_the_metric_carries_none_and_the_dimension_and_fact_do_not(self) -> None:
        """
        Three roles, one render, three different answers.

        ``ast.unparse`` rather than ``endswith('| None')``: the claim is about the annotation
        Python sees, and a substring test would be satisfied by a comment or by a ``| None``
        buried inside some larger expression.
        """
        query = (
            AliasSales.query()
            .metrics(AliasSales.revenue)
            .dimensions(AliasSales.country, AliasSales.unit_price)
        )
        probed = _probed(
            "DuckDBDialect",
            query,
            [
                ("revenue", pyarrow.decimal128(38, 2)),
                ("country", pyarrow.string()),
                ("unit_price", pyarrow.float64()),
            ],
        )

        source = render_dtos([probed], backend_label="duckdb")

        assert _annotations(source, "RevenueByCountry") == {
            "revenue": "decimal.Decimal | None",
            "country": "str",
            "unit_price": "float",
        }


class TestAnAliasThatCannotBindIsAnError:
    """
    A field the probed schema carries no column for stops codegen rather than guessing.

    The alternative failure is much later and much worse: a DTO whose alias never binds is
    accepted by the generator, committed, and then reports ``missing`` at ``.into()`` time in
    a service, with nothing pointing back at the generated file. Raising here puts the field
    name, every candidate tried and the schema's own column names in one message.
    """

    def test_a_field_with_no_matching_column_names_itself_and_the_schema(self) -> None:
        """The message carries the field, the candidates and what the result really held."""
        probed = _probed(
            "DuckDBDialect",
            _alias_sales_query(),
            [("revenue", pyarrow.decimal128(38, 2)), ("nation", pyarrow.string())],
        )

        with pytest.raises(ValueError) as excinfo:
            render_dtos([probed], backend_label="duckdb")

        message = str(excinfo.value)
        assert "'country'" in message
        assert "'nation'" in message
        assert "matches no result column" in message

    def test_a_duplicated_column_name_reports_ambiguity_rather_than_moving_on(self) -> None:
        """
        Two columns under one name is an error, not a reason to try the next candidate.

        ``get_field_index`` answers ``-1`` both for a name the schema lacks and for one it
        carries twice, and collapsing those would let the field bind to whichever candidate
        came next — a different column than the one it named.
        """
        probed = _probed(
            "DuckDBDialect",
            _alias_sales_query(),
            [
                ("revenue", pyarrow.decimal128(38, 2)),
                ("country", pyarrow.string()),
                ("country", pyarrow.string()),
            ],
        )

        with pytest.raises(ValueError) as excinfo:
            render_dtos([probed], backend_label="duckdb")

        assert "matches 2 result columns" in str(excinfo.value)


class TestALeadingUnderscoreFieldNameIsRefused:
    """
    Pydantic forbids a field name starting with ``_``, so generating one is not an option.

    Emitting it anyway produces a file that raises ``NameError`` on *import* -- "Fields must
    not use names with leading underscores" -- a long way from the model attribute that
    caused it. The name is the model's, and the model has ``source=`` for exactly this: the
    warehouse column keeps its spelling while the Python attribute gets a legal one.
    """

    def test_the_field_the_alias_and_the_way_out_are_all_named(self) -> None:
        """The message has to carry the fix, since the field name is the user's to change."""
        query = (
            UnderscoreSales.query().dimensions(UnderscoreSales._id).metrics(UnderscoreSales.revenue)
        )
        probed = _probed(
            "DuckDBDialect",
            query,
            [("revenue", pyarrow.decimal128(38, 2)), ("_id", pyarrow.string())],
        )

        with pytest.raises(ValueError) as excinfo:
            render_dtos([probed], backend_label="duckdb")

        message = str(excinfo.value)
        assert "'_id'" in message
        assert "leading underscore" in message
        assert "source=" in message


class TestAWarehouseShapedAliasStaysInsideItsLiteral:
    """
    Threat T-50-01: the alias is warehouse-controlled text in a file users import.

    The documented workflow redirects generated source to a file and imports it, so a value
    that closes its own string literal is module-level code execution rather than a
    formatting bug. Snowflake's ordinary metric column already carries a double quote, which
    is what makes this a live concern rather than a hypothetical one.
    """

    def test_a_result_column_carrying_quotes_and_a_newline_injects_no_statement(self) -> None:
        """
        A hostile column name round-trips through the literal and adds nothing to the module.

        Asserted structurally: the parsed module body is imports plus exactly one class. A
        payload that escaped its literal would show up as an extra statement, which no
        substring search over the source would notice.
        """
        payload = 'x"\n"""\nimport os\n'

        class Injected(SemanticView, view="dto_alias_injected"):
            revenue = Metric[int](source=payload)
            country = Dimension[str]()

        probed = _probed(
            "DuckDBDialect",
            Injected.query().metrics(Injected.revenue).dimensions(Injected.country),
            [(payload, pyarrow.decimal128(38, 2)), ("country", pyarrow.string())],
            class_name="Injected",
        )

        source = render_dtos([probed], backend_label="duckdb")

        assert _aliases(source, "Injected")["revenue"] == payload
        body = ast.parse(source).body
        assert all(
            isinstance(node, ast.Import | ast.ImportFrom | ast.Expr | ast.ClassDef) for node in body
        ), source
        assert sum(isinstance(node, ast.ClassDef) for node in body) == 1, source


class TestAClassNameThatIsNotAnIdentifierIsRefused:
    """
    The other half of threat T-50-01: the one interpolation site nothing can escape.

    The class above proves a hostile *alias* stays inside its literal. A class name has no
    literal to stay inside — the template writes ``class {{ model.class_name }}(...)`` as a
    bare token — so the equivalent guarantee has to be a refusal rather than a quoting rule.

    Enforced on ``ProbedQuery`` itself rather than inside ``render_dtos``, because the CLI's
    own ``--name`` check does not cover the library path: ``ProbedQuery`` is a public frozen
    dataclass anything can construct, and ``probe_query`` takes ``class_name`` directly. The
    invariant belongs where the value is stored, so a ``ProbedQuery`` that exists is one the
    renderer can safely write out.

    There is no separate vacuity guard here: every other test in this module renders through
    the same constructor with an ordinary name, so a check that refused everything would take
    the whole file down with it.
    """

    def test_the_payload_is_executable_code_rather_than_a_syntax_error(self) -> None:
        """
        The claim that makes the refusal worth having: interpolated, this payload *parses*.

        Stated as a parse of the template's own line shape rather than asserted about the
        renderer, because it is a fact about the payload, not about Semolina — and it is the
        fact that separates "the generated file breaks" from "the generated file runs
        ``os.system`` when the user imports it". Two classes and an ``import`` where the
        template wrote one class and no import.
        """
        module = ast.parse(f"class {INJECTING_CLASS_NAME}(pydantic.BaseModel):\n    pass\n")

        assert sum(isinstance(node, ast.ClassDef) for node in module.body) == 2, ast.dump(module)
        assert any(isinstance(node, ast.Import) for node in module.body), ast.dump(module)

    @pytest.mark.parametrize("class_name", NON_IDENTIFIER_CLASS_NAMES)
    def test_building_a_probed_query_with_one_refuses_it(self, class_name: str) -> None:
        """
        Four shapes, four different rules doing the work.

        ``statement-injection`` is the threat; ``no-whitespace`` is the same threat without a
        space in it, so a fix that split on whitespace cannot pass; ``keyword`` is the case
        ``str.isidentifier`` gets wrong on its own, answering ``True`` for ``'class'``; and
        ``empty`` is what the derived path produces for a dotted path with no attribute part.
        """
        with pytest.raises(ValueError) as excinfo:
            _probed(
                "DuckDBDialect",
                _alias_sales_query(),
                _measured_columns("DuckDBDialect"),
                class_name=class_name,
            )

        assert "not a valid Python identifier" in str(excinfo.value)


class TestAnUnmappedArrowTypeBecomesAnyPlusATodo:
    """
    D-06's other half: no clean Python equivalent means ``Any``, never a guess.

    ``arrow_type_to_python`` answers ``None`` for interval, duration, struct, map, list,
    union and null — and for whatever ``pyarrow`` adds next, which is the case that matters,
    because a renderer that guessed would guess silently for a type nobody has looked at yet.
    The project already carries one known-wrong guess on purpose:
    ``_DUCKDB_TYPE_MAP['INTERVAL']`` still reads ``datetime.timedelta`` and is left unfixed
    (broken window 6) so two maps are not wrong in step. Reproducing that here would turn a
    disagreement into an apparent consensus.
    """

    def test_a_struct_column_renders_any_and_names_its_arrow_type_in_a_comment(self) -> None:
        """The annotation is ``Any``, the type is named in a comment, and typing is imported."""
        probed = _probed(
            "DuckDBDialect",
            _alias_sales_query(),
            [
                ("revenue", pyarrow.decimal128(38, 2)),
                ("country", pyarrow.struct([("iso", pyarrow.string())])),
            ],
        )

        source = render_dtos([probed], backend_label="duckdb")

        assert _annotations(source, "RevenueByCountry")["country"] == "Any"
        assert _comment_above(source, "country") == "# TODO: struct<iso: string>"
        assert "from typing import Any" in _import_statements(source)

    def test_an_arrow_type_whose_own_text_spans_two_lines_is_collapsed_into_one_comment(
        self,
    ) -> None:
        r"""
        A newline inside a nested field name cannot break the generated file.

        ``str(pyarrow.struct([pyarrow.field('a\nb', ...)]))`` really does carry a newline —
        nested field names come from the warehouse, so the Arrow type's own text is
        warehouse-controlled just as the alias is. Uncollapsed, the second half would land on
        its own physical line below a ``#`` and be parsed as code: this exact input produces
        a ``SyntaxError`` without the split-and-rejoin, so ``ast.parse`` is a real guard here
        rather than a formality.
        """
        nested = pyarrow.struct([pyarrow.field("a\nb", pyarrow.int64())])
        assert "\n" in str(nested), "the guard is vacuous unless the type's own text wraps"
        probed = _probed(
            "DuckDBDialect",
            _alias_sales_query(),
            [("revenue", pyarrow.decimal128(38, 2)), ("country", nested)],
        )

        source = render_dtos([probed], backend_label="duckdb")

        # The parse comes first deliberately: uncollapsed, this source raises `SyntaxError:
        # expected an indented block after class definition` (measured), and that is the
        # failure worth reporting. The comment's text is the weaker, second claim.
        assert _annotations(source, "RevenueByCountry")["country"] == "Any"
        assert _comment_above(source, "country") == "# TODO: struct<a b: int64>"


class TestTheImportBlockFollowsTheResolvedAnnotations:
    """
    Imports are derived from the strings the template writes, not from the ones before it.

    A metric annotation gains ``| None`` during context building, so an equality test against
    the prefix map would drop ``import decimal`` for exactly the fields that need it and the
    generated module would raise ``NameError`` on import — for metrics alone. Substring
    containment is the rule, and ``python_renderer`` states the same reason in the same
    words.
    """

    def test_a_decimal_metric_pulls_in_decimal_despite_its_none_suffix(self) -> None:
        """``decimal.Decimal | None`` still imports ``decimal``."""
        probed = _probed(
            "DuckDBDialect",
            AliasSales.query().metrics(AliasSales.revenue),
            [("revenue", pyarrow.decimal128(38, 2))],
        )

        source = render_dtos([probed], backend_label="duckdb")

        assert _annotations(source, "RevenueByCountry") == {"revenue": "decimal.Decimal | None"}
        assert "import decimal" in _import_statements(source)

    def test_a_timestamp_dimension_pulls_in_datetime(self) -> None:
        """The undecorated half of the same rule, so the two prefixes are both exercised."""
        probed = _probed(
            "DuckDBDialect",
            AliasSales.query().dimensions(AliasSales.country),
            [("country", pyarrow.timestamp("us"))],
        )

        source = render_dtos([probed], backend_label="duckdb")

        assert _annotations(source, "RevenueByCountry") == {"country": "datetime.datetime"}
        assert "import datetime" in _import_statements(source)

    def test_the_generated_module_imports_nothing_from_semolina(self) -> None:
        """
        A generated DTO is a plain Pydantic model with no Semolina dependency at runtime.

        That is what lets it be committed into a service which only reads results, and it is
        what makes plan 50-04's isolated type check meaningful — a file that imported
        Semolina would be checked against this repo's own package rather than on its own
        terms.
        """
        probed = _probed("DuckDBDialect", _alias_sales_query(), _measured_columns("DuckDBDialect"))

        source = render_dtos([probed], backend_label="duckdb")

        assert not [
            module
            for module in _imported_modules(source)
            if module == "semolina" or module.startswith("semolina.")
        ], source

    def test_deferred_annotations_are_enabled_before_any_other_import(self) -> None:
        """
        ``from __future__ import annotations`` leads the block, which Python requires.

        Emitted unconditionally: every metric annotation is a ``T | None`` union, which is
        3.10+ syntax evaluated eagerly, and a generated DTO is meant to be committed into a
        service this repo knows nothing about.
        """
        probed = _probed("DuckDBDialect", _alias_sales_query(), _measured_columns("DuckDBDialect"))

        source = render_dtos([probed], backend_label="duckdb")

        assert _import_statements(source)[0] == "from __future__ import annotations"


class TestSeveralDtosRenderIntoOneFile:
    """
    O-03, settled by matching what model codegen already does and already documents.

    ``docs/src/how-to/codegen.rst``: *"All classes appear in one output block with a single
    shared imports section."* The renderer's signature already takes a list, so any other
    answer would need a reason rather than this one needing a justification.
    """

    def test_two_queries_yield_one_import_block_and_two_classes(self) -> None:
        """
        Imports appear once, before both classes, and each class keeps its own provenance.

        The two probes report *different* routes on purpose: a per-class docstring built from
        a module-level value would pass a same-route test and be wrong the first time a
        zero-row fallback fired beside a primary probe.
        """
        first = _probed(
            "DuckDBDialect",
            _alias_sales_query(),
            _measured_columns("DuckDBDialect"),
            class_name="RevenueByCountry",
            origin="myapp.queries.revenue_by_country",
        )
        second = _probed(
            "DuckDBDialect",
            AliasSales.query().dimensions(AliasSales.country),
            [("country", pyarrow.string())],
            class_name="CountryList",
            origin="myapp.queries.country_list",
            route=ROUTE_ZERO_ROW,
        )

        source = render_dtos([first, second], backend_label="duckdb")

        body = ast.parse(source).body
        classes = [node for node in body if isinstance(node, ast.ClassDef)]
        assert [node.name for node in classes] == ["RevenueByCountry", "CountryList"]

        imports = [
            index
            for index, node in enumerate(body)
            if isinstance(node, ast.Import | ast.ImportFrom)
        ]
        first_class = next(
            index for index, node in enumerate(body) if isinstance(node, ast.ClassDef)
        )
        assert max(imports) < first_class, source
        statements = _import_statements(source)
        assert len(statements) == len(set(statements)), source

        assert ast.get_docstring(classes[0]) == (
            f"Result DTO for myapp.queries.revenue_by_country (probe route: "
            f"{ROUTE_EXECUTE_SCHEMA})."
        )
        assert ast.get_docstring(classes[1]) == (
            f"Result DTO for myapp.queries.country_list (probe route: {ROUTE_ZERO_ROW})."
        )
