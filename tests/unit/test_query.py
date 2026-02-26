"""
Tests for Query builder with immutability and method chaining.

Tests cover:
- QRY-01: .metrics() accepts Metric fields only
- QRY-02: .dimensions() accepts Dimension fields
- QRY-03: .dimensions() accepts Fact fields
- QRY-04: .where() accepts Predicate objects and combines with AND
- QRY-05: .order_by() accepts Field instances
- QRY-06: .limit() accepts positive integers
- QRY-07: Query immutability (frozen dataclass)
- QRY-08: Method chaining returns new instances

Phase 10.1 tests:
- Model.query() as primary entry point (model-centric API)
- .where() method for Pythonic filtering with field operators
- Field ownership validation preventing cross-model field mixing
- .execute() for eager execution returning Result objects
- Field operators: ==, !=, <, <=, >, >= returning Predicate nodes

Phase 13.1 tests:
- where() varargs: multiple conditions ANDed together
- where() None filtering: None values silently ignored
- Predicate-based filter assertions (And, Or, Not, Exact, Gt, etc.)
"""

import pytest

from cubano import Dimension, Fact, Metric, SemanticView
from cubano.engines.mock import MockEngine
from cubano.fields import NullsOrdering, OrderTerm
from cubano.filters import And, Exact, Gt, Or, Predicate
from cubano.query import _Query
from cubano.results import Result


class Sales(SemanticView, view="sales_view"):
    """Test model for query tests."""

    revenue = Metric()
    cost = Metric()
    country = Dimension()
    region = Dimension()
    unit_price = Fact()


class TestQueryMetrics:
    """Test .metrics() method (QRY-01)."""

    def test_metrics_single_field(self):
        """Should accept single Metric field."""
        q = _Query().metrics(Sales.revenue)
        assert q._metrics == (Sales.revenue,)

    def test_metrics_multiple_fields(self):
        """Should accept multiple Metric fields."""
        q = _Query().metrics(Sales.revenue, Sales.cost)
        assert q._metrics == (Sales.revenue, Sales.cost)

    def test_metrics_rejects_dimension(self):
        """Should reject Dimension fields with helpful error."""
        with pytest.raises(TypeError) as exc_info:
            _Query().metrics(Sales.country)
        assert "Did you mean .dimensions()?" in str(exc_info.value)

    def test_metrics_rejects_fact(self):
        """Should reject Fact fields with helpful error."""
        with pytest.raises(TypeError) as exc_info:
            _Query().metrics(Sales.unit_price)
        assert "Did you mean .dimensions()?" in str(exc_info.value)

    def test_metrics_empty_raises_error(self):
        """Should reject empty call."""
        with pytest.raises(ValueError) as exc_info:
            _Query().metrics()
        assert "At least one metric" in str(exc_info.value)

    def test_metrics_accumulates(self):
        """Multiple .metrics() calls should accumulate, not replace."""
        q = _Query().metrics(Sales.revenue).metrics(Sales.cost)
        assert q._metrics == (Sales.revenue, Sales.cost)


class TestQueryDimensions:
    """Test .dimensions() method (QRY-02, QRY-03)."""

    def test_dimensions_single_dimension(self):
        """Should accept single Dimension field."""
        q = _Query().dimensions(Sales.country)
        assert q._dimensions == (Sales.country,)

    def test_dimensions_multiple_dimensions(self):
        """Should accept multiple Dimension fields."""
        q = _Query().dimensions(Sales.country, Sales.region)
        assert q._dimensions == (Sales.country, Sales.region)

    def test_dimensions_accepts_fact(self):
        """Should accept Fact fields (QRY-03)."""
        q = _Query().dimensions(Sales.unit_price)
        assert q._dimensions == (Sales.unit_price,)

    def test_dimensions_mixed_dimension_and_fact(self):
        """Should accept both Dimension and Fact together."""
        q = _Query().dimensions(Sales.country, Sales.unit_price)
        assert q._dimensions == (Sales.country, Sales.unit_price)

    def test_dimensions_rejects_metric(self):
        """Should reject Metric fields with helpful error."""
        with pytest.raises(TypeError) as exc_info:
            _Query().dimensions(Sales.revenue)
        assert "Did you mean .metrics()?" in str(exc_info.value)

    def test_dimensions_empty_raises_error(self):
        """Should reject empty call."""
        with pytest.raises(ValueError) as exc_info:
            _Query().dimensions()
        assert "At least one dimension" in str(exc_info.value)

    def test_dimensions_accumulates(self):
        """Multiple .dimensions() calls should accumulate, not replace."""
        q = _Query().dimensions(Sales.country).dimensions(Sales.region)
        assert q._dimensions == (Sales.country, Sales.region)


class TestQueryFilter:
    """Test .where() method (QRY-04)."""

    def test_filter_single_predicate(self):
        """Should accept Predicate object."""
        q = _Query().where(Exact("country", "US"))
        assert q._filters is not None
        assert isinstance(q._filters, Exact)

    def test_filter_combines_with_and(self):
        """Multiple .where() calls should AND together."""
        q1 = _Query().where(Exact("country", "US"))
        q2 = q1.where(Exact("region", "West"))

        # Should be combined with AND
        assert q2._filters is not None
        assert isinstance(q2._filters, And)

    def test_filter_varargs(self):
        """where() should accept multiple conditions as varargs."""
        q = _Query().where(Exact("country", "US"), Gt("revenue", 1000))
        assert q._filters is not None
        assert isinstance(q._filters, And)

    def test_filter_varargs_single(self):
        """where() with single vararg should produce that predicate directly."""
        q = _Query().where(Exact("country", "US"))
        assert q._filters is not None
        assert isinstance(q._filters, Exact)

    def test_filter_none_is_no_op(self):
        """where(None) should return same instance."""
        q1 = _Query().metrics(Sales.revenue)
        q2 = q1.where(None)
        assert q1 is q2

    def test_filter_no_args_is_no_op(self):
        """where() with no args should return same instance."""
        q1 = _Query().metrics(Sales.revenue)
        q2 = q1.where()
        assert q1 is q2

    def test_filter_varargs_with_none(self):
        """where() should ignore None values among varargs."""
        q = _Query().where(Exact("a", 1), None, Gt("b", 2))
        assert q._filters is not None
        assert isinstance(q._filters, And)

    def test_filter_all_none_is_no_op(self):
        """where(None, None, None) should return same instance."""
        q1 = _Query().metrics(Sales.revenue)
        q2 = q1.where(None, None, None)
        assert q1 is q2


class TestQueryOrderBy:
    """Test .order_by() method (QRY-05)."""

    def test_order_by_single_field(self):
        """Should accept single Field."""
        q = _Query().order_by(Sales.revenue)
        assert q._order_by_fields == (Sales.revenue,)

    def test_order_by_multiple_fields(self):
        """Should accept multiple Fields."""
        q = _Query().order_by(Sales.revenue, Sales.country)
        assert q._order_by_fields == (Sales.revenue, Sales.country)

    def test_order_by_accepts_any_field_type(self):
        """Should accept Metric, Dimension, or Fact."""
        q = _Query().order_by(Sales.revenue, Sales.country, Sales.unit_price)
        assert q._order_by_fields == (Sales.revenue, Sales.country, Sales.unit_price)

    def test_order_by_rejects_non_field(self):
        """Should reject non-Field objects."""
        with pytest.raises(TypeError) as exc_info:
            _Query().order_by("revenue")
        assert "requires Field" in str(exc_info.value)

    def test_order_by_empty_raises_error(self):
        """Should reject empty call."""
        with pytest.raises(ValueError) as exc_info:
            _Query().order_by()
        assert "At least one field" in str(exc_info.value)

    def test_order_by_accumulates(self):
        """Multiple .order_by() calls should accumulate, not replace."""
        q = _Query().order_by(Sales.revenue).order_by(Sales.country)
        assert q._order_by_fields == (Sales.revenue, Sales.country)

    def test_order_by_descending(self):
        """_Query().order_by(Sales.revenue.desc()) should store OrderTerm."""
        q = _Query().order_by(Sales.revenue.desc())
        assert len(q._order_by_fields) == 1
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert q._order_by_fields[0].field is Sales.revenue
        assert q._order_by_fields[0].descending is True

    def test_order_by_ascending_explicit(self):
        """_Query().order_by(Sales.revenue.asc()) should store OrderTerm."""
        q = _Query().order_by(Sales.revenue.asc())
        assert len(q._order_by_fields) == 1
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert q._order_by_fields[0].field is Sales.revenue
        assert q._order_by_fields[0].descending is False

    def test_order_by_with_nulls_first(self):
        """_Query().order_by() with desc(NullsOrdering.FIRST) stores nulls=FIRST."""
        q = _Query().order_by(Sales.revenue.desc(NullsOrdering.FIRST))
        assert len(q._order_by_fields) == 1
        term = q._order_by_fields[0]
        assert isinstance(term, OrderTerm)
        assert term.nulls == NullsOrdering.FIRST

    def test_order_by_with_nulls_last(self):
        """_Query().order_by() with asc(NullsOrdering.LAST) stores nulls=LAST."""
        q = _Query().order_by(Sales.revenue.asc(NullsOrdering.LAST))
        assert len(q._order_by_fields) == 1
        term = q._order_by_fields[0]
        assert isinstance(term, OrderTerm)
        assert term.nulls == NullsOrdering.LAST

    def test_order_by_mixed_directions(self):
        """_Query().order_by() with desc() and asc() stores both OrderTerms."""
        q = _Query().order_by(Sales.revenue.desc(), Sales.country.asc())
        assert len(q._order_by_fields) == 2
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert isinstance(q._order_by_fields[1], OrderTerm)
        assert q._order_by_fields[0].descending is True
        assert q._order_by_fields[1].descending is False

    def test_order_by_mixed_nulls_handling(self):
        """_Query().order_by() with mixed NULLS FIRST/LAST stores both correctly."""
        q = _Query().order_by(
            Sales.revenue.desc(NullsOrdering.FIRST), Sales.country.asc(NullsOrdering.LAST)
        )
        assert len(q._order_by_fields) == 2
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert q._order_by_fields[0].nulls == NullsOrdering.FIRST
        assert isinstance(q._order_by_fields[1], OrderTerm)
        assert q._order_by_fields[1].nulls == NullsOrdering.LAST

    def test_order_by_bare_field_still_works(self):
        """_Query().order_by(Sales.revenue) continues to work (backward compatible)."""
        q = _Query().order_by(Sales.revenue)
        assert q._order_by_fields == (Sales.revenue,)
        # Bare field stored as-is, not wrapped in OrderTerm
        assert isinstance(q._order_by_fields[0], Metric)

    def test_order_by_mixed_field_and_order_term(self):
        """_Query().order_by() accepts mix of OrderTerm and bare Field."""
        q = _Query().order_by(Sales.revenue.desc(), Sales.country)
        assert len(q._order_by_fields) == 2
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert isinstance(q._order_by_fields[1], Dimension)


class TestQueryLimit:
    """Test .limit() method (QRY-06)."""

    def test_limit_positive_integer(self):
        """Should accept positive integers."""
        q = _Query().limit(100)
        assert q._limit_value == 100

    def test_limit_rejects_zero(self):
        """Should reject zero."""
        with pytest.raises(ValueError) as exc_info:
            _Query().limit(0)
        assert "positive integer" in str(exc_info.value)

    def test_limit_rejects_negative(self):
        """Should reject negative values."""
        with pytest.raises(ValueError) as exc_info:
            _Query().limit(-10)
        assert "positive integer" in str(exc_info.value)

    def test_limit_rejects_float(self):
        """Should reject float values."""
        with pytest.raises(TypeError) as exc_info:
            _Query().limit(3.14)
        assert "requires int" in str(exc_info.value)


class TestQueryImmutability:
    """Test Query immutability (QRY-07)."""

    def test_query_is_frozen(self):
        """Query should be a frozen dataclass."""
        q = _Query()
        # Attempt to modify should raise (frozen dataclass raises FrozenInstanceError)
        with pytest.raises((AttributeError, TypeError)):
            q._metrics = (Sales.revenue,)  # type: ignore[misc]

    def test_metrics_returns_new_instance(self):
        """metrics() should return new instance, original unchanged."""
        q1 = _Query()
        q2 = q1.metrics(Sales.revenue)

        assert q1._metrics == ()
        assert q2._metrics == (Sales.revenue,)
        assert q1 is not q2

    def test_dimensions_returns_new_instance(self):
        """dimensions() should return new instance, original unchanged."""
        q1 = _Query()
        q2 = q1.dimensions(Sales.country)

        assert q1._dimensions == ()
        assert q2._dimensions == (Sales.country,)
        assert q1 is not q2

    def test_filter_returns_new_instance(self):
        """where() should return new instance, original unchanged."""
        q1 = _Query()
        q2 = q1.where(Sales.country == "US")

        assert q1._filters is None
        assert q2._filters is not None
        assert q1 is not q2

    def test_order_by_returns_new_instance(self):
        """order_by() should return new instance, original unchanged."""
        q1 = _Query()
        q2 = q1.order_by(Sales.revenue)

        assert q1._order_by_fields == ()
        assert q2._order_by_fields == (Sales.revenue,)
        assert q1 is not q2

    def test_limit_returns_new_instance(self):
        """limit() should return new instance, original unchanged."""
        q1 = _Query()
        q2 = q1.limit(100)

        assert q1._limit_value is None
        assert q2._limit_value == 100
        assert q1 is not q2


class TestQueryChaining:
    """Test method chaining (QRY-08)."""

    def test_full_method_chain(self):
        """Should support full method chain."""
        q = (
            _Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country, Sales.region)
            .where((Sales.country == "US") | (Sales.country == "CA"))
            .order_by(Sales.revenue)
            .limit(100)
        )

        assert q._metrics == (Sales.revenue, Sales.cost)
        assert q._dimensions == (Sales.country, Sales.region)
        assert q._filters is not None
        assert q._order_by_fields == (Sales.revenue,)
        assert q._limit_value == 100

    def test_partial_chain_preserves_immutability(self):
        """Intermediate chains should not affect earlier queries."""
        base = _Query().metrics(Sales.revenue)
        with_dims = base.dimensions(Sales.country)
        filtered = with_dims.where(Sales.country == "US")

        # Base should be unchanged
        assert base._dimensions == ()
        assert base._filters is None

        # with_dims should have dimensions but no filter
        assert with_dims._dimensions == (Sales.country,)
        assert with_dims._filters is None

        # Only filtered should have all
        assert filtered._dimensions == (Sales.country,)
        assert filtered._filters is not None

    def test_full_chain_with_descending(self):
        """Full method chain using .desc() and nulls handling should work end to end."""
        q = (
            _Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
            .order_by(Sales.revenue.desc(NullsOrdering.FIRST), Sales.country.asc())
            .limit(100)
        )

        assert len(q._order_by_fields) == 2
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert q._order_by_fields[0].descending is True
        assert q._order_by_fields[0].nulls == NullsOrdering.FIRST
        assert isinstance(q._order_by_fields[1], OrderTerm)
        assert q._order_by_fields[1].descending is False


class TestQueryValidation:
    """Test _validate_for_execution() method."""

    def test_empty_query_validation_fails(self):
        """Empty query should fail validation."""
        q = _Query()
        with pytest.raises(ValueError) as exc_info:
            q._validate_for_execution()
        assert "at least one metric or dimension" in str(exc_info.value)

    def test_query_with_metrics_validates(self):
        """Query with metrics should pass validation."""
        q = _Query().metrics(Sales.revenue)
        # Should not raise
        q._validate_for_execution()

    def test_query_with_dimensions_validates(self):
        """Query with dimensions should pass validation."""
        q = _Query().dimensions(Sales.country)
        # Should not raise
        q._validate_for_execution()

    def test_query_with_both_validates(self):
        """Query with both metrics and dimensions should pass validation."""
        q = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        # Should not raise
        q._validate_for_execution()


class TestQueryStubs:
    """Test stub methods for future phases."""

    def test_to_sql_validates_then_generates_sql(self):
        """to_sql() should validate, then generate SQL."""
        # Empty query should fail validation first
        q_empty = _Query()
        with pytest.raises(ValueError):
            q_empty.to_sql()

        # Valid query should generate SQL using MockDialect
        q_valid = _Query().metrics(Sales.revenue)
        sql = q_valid.to_sql()
        assert isinstance(sql, str)
        assert "SELECT" in sql
        assert 'AGG("revenue")' in sql
        assert 'FROM "sales_view"' in sql

    def test_execute_validates_then_raises(self):
        """execute() should validate, then raise if no engine registered."""
        # Empty query should fail validation first
        q_empty = _Query()
        with pytest.raises(ValueError, match="must select at least one metric or dimension"):
            q_empty.execute()

        # Valid query with no engine registered should raise ValueError
        q_valid = _Query().metrics(Sales.revenue)
        with pytest.raises(ValueError, match="No engine registered"):
            q_valid.execute()


class TestQueryUsing:
    """Test Query.using() method for per-query engine selection."""

    def test_using_returns_new_query(self):
        """using() should return new Query instance (immutability)."""
        q1 = _Query().metrics(Sales.revenue)
        q2 = q1.using("warehouse")
        assert q1 is not q2
        assert q1._using is None
        assert q2._using == "warehouse"

    def test_using_stores_engine_name(self):
        """using() should store engine name for lazy resolution."""
        q = _Query().metrics(Sales.revenue).using("my_engine")
        assert q._using == "my_engine"

    def test_using_with_non_string_raises(self):
        """using() should reject non-string arguments."""
        q = _Query().metrics(Sales.revenue)
        with pytest.raises(TypeError, match="requires engine name string"):
            q.using(123)
        with pytest.raises(TypeError, match="requires engine name string"):
            q.using(None)

    def test_using_chainable(self):
        """using() should be chainable with other query methods."""
        q = _Query().metrics(Sales.revenue).using("warehouse").dimensions(Sales.country)
        assert q._using == "warehouse"
        assert len(q._metrics) == 1
        assert len(q._dimensions) == 1

    def test_using_can_be_called_anywhere_in_chain(self):
        """using() should work at any position in method chain."""
        q1 = _Query().using("warehouse").metrics(Sales.revenue)
        q2 = _Query().metrics(Sales.revenue).using("warehouse")
        assert q1._using == q2._using == "warehouse"


class TestQueryFetch:
    """Test Query.execute() execution pipeline with registry integration."""

    def test_fetch_returns_row_objects(self):
        """execute() should return Result wrapping Row objects."""
        import cubano

        engine = MockEngine()
        engine.load("sales_view", [{"revenue": 1000, "country": "US"}])
        cubano.register("default", engine)

        results = _Query().metrics(Sales.revenue).execute()
        from cubano import Row
        from cubano.results import Result

        assert isinstance(results, Result)
        assert len(results) == 1
        assert isinstance(results[0], Row)

    def test_fetch_row_attribute_access(self):
        """Result rows should support attribute access."""
        import cubano

        engine = MockEngine()
        engine.load("sales_view", [{"revenue": 1000, "country": "US"}])
        cubano.register("default", engine)

        results = _Query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        assert results[0].revenue == 1000
        assert results[0].country == "US"

    def test_fetch_row_dict_access(self):
        """Result rows should support dict-style access."""
        import cubano

        engine = MockEngine()
        engine.load("sales_view", [{"revenue": 500, "country": "CA"}])
        cubano.register("default", engine)

        results = _Query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        assert results[0]["revenue"] == 500
        assert results[0]["country"] == "CA"

    def test_fetch_with_default_engine(self):
        """execute() without using() should use default engine."""
        import cubano

        engine = MockEngine()
        engine.load("sales_view", [{"revenue": 1000}])
        cubano.register("default", engine)

        results = _Query().metrics(Sales.revenue).execute()
        assert len(results) == 1
        assert results[0].revenue == 1000

    def test_fetch_with_named_engine(self):
        """execute() with using() should use named engine."""
        import cubano

        engine = MockEngine()
        engine.load("sales_view", [{"revenue": 2000}])
        cubano.register("warehouse", engine)

        results = _Query().metrics(Sales.revenue).using("warehouse").execute()
        assert len(results) == 1
        assert results[0].revenue == 2000

    def test_fetch_no_engine_raises(self):
        """execute() with no engines registered should raise ValueError."""
        q = _Query().metrics(Sales.revenue)
        with pytest.raises(ValueError, match="No engine registered"):
            q.execute()

    def test_fetch_wrong_engine_name_raises(self):
        """execute() with non-existent engine name should raise ValueError."""
        import cubano

        engine = MockEngine()
        cubano.register("default", engine)

        q = _Query().metrics(Sales.revenue).using("other")
        with pytest.raises(ValueError, match="No engine registered with name 'other'"):
            q.execute()

    def test_fetch_empty_query_raises(self):
        """execute() on empty query should raise ValueError."""
        import cubano

        engine = MockEngine()
        cubano.register("default", engine)

        q = _Query()
        with pytest.raises(ValueError, match="must select at least one metric or dimension"):
            q.execute()

    def test_fetch_empty_fixtures(self):
        """execute() with no fixtures loaded should return empty Result."""
        import cubano

        engine = MockEngine()  # No fixtures loaded
        cubano.register("default", engine)

        results = _Query().metrics(Sales.revenue).execute()
        assert len(results) == 0

    def test_fetch_lazy_resolution(self):
        """Engine should be resolved at execute() time, not during query construction."""
        import cubano

        # Create query BEFORE registering engine
        q = _Query().metrics(Sales.revenue).using("later")

        # Register engine AFTER query creation
        engine = MockEngine()
        engine.load("sales_view", [{"revenue": 1500}])
        cubano.register("later", engine)

        # execute() should succeed (proves lazy resolution)
        results = q.execute()
        assert len(results) == 1
        assert results[0].revenue == 1500


class TestQueryFetchIntegration:
    """Integration tests for full query execution pipeline."""

    def test_full_pipeline(self):
        """Test complete pipeline: define model, build query, register engine, fetch results."""
        import cubano

        # Register engine with fixture data
        engine = MockEngine()
        engine.load(
            "sales_view",
            [
                {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
                {"revenue": 2000, "cost": 200, "country": "CA", "region": "West"},
                {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
            ],
        )
        cubano.register("default", engine)

        # Build and execute query
        results = (
            _Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country)
            .limit(10)
            .execute()
        )

        # Verify Row objects with proper access patterns
        assert len(results) == 3
        assert results[0].revenue == 1000
        assert results[0]["cost"] == 100
        assert results[1].country == "CA"

    def test_multiple_engines(self):
        """Should select correct engine based on using()."""
        import cubano

        # Register two engines with different data
        engine1 = MockEngine()
        engine1.load("sales_view", [{"revenue": 1000}])
        cubano.register("engine1", engine1)

        engine2 = MockEngine()
        engine2.load("sales_view", [{"revenue": 9999}])
        cubano.register("engine2", engine2)

        # Same query, different engines
        q = _Query().metrics(Sales.revenue)

        results1 = q.using("engine1").execute()
        assert results1[0].revenue == 1000

        results2 = q.using("engine2").execute()
        assert results2[0].revenue == 9999

    def test_query_reuse_with_different_engines(self):
        """Same query instance can be executed with different engines."""
        import cubano

        # Register two engines
        engine1 = MockEngine()
        engine1.load("sales_view", [{"revenue": 100}])
        cubano.register("prod", engine1)

        engine2 = MockEngine()
        engine2.load("sales_view", [{"revenue": 200}])
        cubano.register("test", engine2)

        # Create base query once
        base_query = _Query().metrics(Sales.revenue).dimensions(Sales.country)

        # Execute against different engines
        prod_results = base_query.using("prod").execute()
        test_results = base_query.using("test").execute()

        assert prod_results[0].revenue == 100
        assert test_results[0].revenue == 200


class TestModelCentricAPI:
    """Test Phase 10.1 model-centric API (Model.query() entry point)."""

    def test_model_query_creates_bound_query(self):
        """Model.query() should create _Query bound to the model."""
        q = Sales.query()
        assert isinstance(q, _Query)
        assert q._model is Sales

    def test_model_query_chainable(self):
        """Model.query() result should support fluent method chaining."""
        q = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).limit(100)
        assert len(q._metrics) == 1
        assert len(q._dimensions) == 1
        assert q._limit_value == 100

    def test_model_query_with_using(self):
        """Model.query(using='name') should set engine name."""
        q = Sales.query(using="warehouse").metrics(Sales.revenue)
        assert q._using == "warehouse"

    def test_model_query_validation_prevents_mixing_fields(self):
        """Model.query() validation should prevent mixing fields from different models."""

        class Orders(SemanticView, view="orders"):
            total = Metric()

        q = Sales.query()
        with pytest.raises(TypeError) as exc_info:
            q.metrics(Orders.total)
        assert "different models" in str(exc_info.value)


class TestQueryWhere:
    """Test Query.where() method for Pythonic filtering."""

    def test_where_accepts_predicate(self):
        """where() should accept Predicate objects."""
        q = _Query().where(Exact("country", "US"))
        assert q._filters is not None
        assert isinstance(q._filters, Predicate)

    def test_where_accepts_none_as_no_op(self):
        """where(None) should be a no-op."""
        q1 = _Query().metrics(Sales.revenue)
        q2 = q1.where(None)
        assert q1 is q2  # Should return same instance for None

    def test_where_combines_multiple_calls_with_and(self):
        """Multiple .where() calls should be ANDed together."""
        q = _Query().where(Exact("country", "US")).where(Exact("region", "West"))
        assert q._filters is not None
        assert isinstance(q._filters, And)

    def test_where_with_field_operators(self):
        """where() should accept Field operators (==, !=, <, etc.)."""
        # Field operators return Predicate objects
        q = _Query().where(Sales.country == "US")
        assert q._filters is not None
        assert isinstance(q._filters, Exact)

    def test_where_with_composed_operators(self):
        """where() should accept composed field operators."""
        q = _Query().where((Sales.country == "US") | (Sales.country == "CA"))
        assert q._filters is not None
        assert isinstance(q._filters, Or)

    def test_where_multiple_calls_and(self):
        """Multiple where() calls should AND together."""
        q = _Query().where(Exact("country", "US")).where(Exact("region", "West"))
        assert q._filters is not None
        assert isinstance(q._filters, And)

    def test_where_varargs_and(self):
        """where() with multiple args should AND them together."""
        q = _Query().where(Sales.country == "US", Sales.revenue > 1000)
        assert q._filters is not None
        assert isinstance(q._filters, And)

    def test_where_varargs_with_none_filtering(self):
        """where() should ignore None values in varargs."""
        q = _Query().where(Sales.country == "US", None, Sales.revenue > 1000)
        assert q._filters is not None
        assert isinstance(q._filters, And)


class TestFieldOperators:
    """Test Field comparison operators returning Predicate nodes (Phase 13.1)."""

    def test_field_equality_returns_exact(self):
        """Field == value should return Exact predicate."""
        pred = Sales.country == "US"
        assert isinstance(pred, Exact)
        assert pred.field_name == "country"
        assert pred.value == "US"

    def test_field_inequality_returns_not_equal(self):
        """Field != value should return NotEqual(...)."""
        from cubano.filters import NotEqual

        pred = Sales.country != "US"
        assert isinstance(pred, NotEqual)
        assert pred.field_name == "country"
        assert pred.value == "US"

    def test_field_less_than_returns_lt(self):
        """Field < value should return Lt predicate."""
        from cubano.filters import Lt

        pred = Sales.revenue < 1000
        assert isinstance(pred, Lt)
        assert pred.field_name == "revenue"
        assert pred.value == 1000

    def test_field_less_equal_returns_lte(self):
        """Field <= value should return Lte predicate."""
        from cubano.filters import Lte

        pred = Sales.revenue <= 1000
        assert isinstance(pred, Lte)
        assert pred.field_name == "revenue"
        assert pred.value == 1000

    def test_field_greater_than_returns_gt(self):
        """Field > value should return Gt predicate."""
        pred = Sales.revenue > 1000
        assert isinstance(pred, Gt)
        assert pred.field_name == "revenue"
        assert pred.value == 1000

    def test_field_greater_equal_returns_gte(self):
        """Field >= value should return Gte predicate."""
        from cubano.filters import Gte

        pred = Sales.revenue >= 1000
        assert isinstance(pred, Gte)
        assert pred.field_name == "revenue"
        assert pred.value == 1000

    def test_operators_compose_with_and(self):
        """Field operators should compose with & (AND)."""
        pred = (Sales.country == "US") & (Sales.revenue > 1000)
        assert isinstance(pred, And)

    def test_operators_compose_with_or(self):
        """Field operators should compose with | (OR)."""
        pred = (Sales.country == "US") | (Sales.country == "CA")
        assert isinstance(pred, Or)


class TestFieldOwnershipValidation:
    """Test field ownership validation for cross-model field mixing."""

    def test_cannot_mix_different_model_fields_in_metrics(self):
        """Should reject metrics from different models."""

        class Orders(SemanticView, view="orders"):
            total = Metric()

        with pytest.raises(TypeError) as exc_info:
            Sales.query().metrics(Sales.revenue, Orders.total)
        assert "different models" in str(exc_info.value)

    def test_cannot_mix_different_model_fields_in_dimensions(self):
        """Should reject dimensions from different models."""

        class Orders(SemanticView, view="orders"):
            region = Dimension()

        with pytest.raises(TypeError) as exc_info:
            Sales.query().dimensions(Sales.country, Orders.region)
        assert "different models" in str(exc_info.value)

    def test_query_from_procedural_api_allows_mixing(self):
        """_Query() constructor (not Model.query()) allows mixing (backward compat)."""
        # Procedural API does NOT set _model, so field ownership validation is skipped
        q = _Query().metrics(Sales.revenue)
        # This would fail if _model is set, but it's not in procedural API
        assert q._model is None


class TestExecuteMethod:
    """Test Query.execute() for eager execution returning Result objects."""

    def test_execute_returns_result(self):
        """execute() should return Result object, not list."""
        import cubano

        engine = MockEngine()
        engine.load("sales_view", [{"revenue": 1000, "country": "US"}])
        cubano.register("default", engine)

        result = Sales.query().metrics(Sales.revenue).execute()
        assert isinstance(result, Result)

    def test_execute_result_has_row_objects(self):
        """Result from execute() should contain Row objects."""
        import cubano

        engine = MockEngine()
        engine.load(
            "sales_view",
            [
                {"revenue": 1000, "country": "US"},
                {"revenue": 2000, "country": "CA"},
            ],
        )
        cubano.register("default", engine)

        result = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        assert len(result) == 2
        assert result[0].revenue == 1000
        assert result[1].country == "CA"

    def test_execute_result_supports_iteration(self):
        """Result from execute() should support iteration."""
        import cubano

        engine = MockEngine()
        engine.load(
            "sales_view",
            [
                {"revenue": 1000, "country": "US"},
                {"revenue": 2000, "country": "CA"},
            ],
        )
        cubano.register("default", engine)

        result = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        rows = list(result)
        assert len(rows) == 2
        assert rows[0].revenue == 1000

    def test_execute_result_supports_indexing(self):
        """Result from execute() should support indexing."""
        import cubano

        engine = MockEngine()
        engine.load(
            "sales_view",
            [
                {"revenue": 1000, "country": "US"},
                {"revenue": 2000, "country": "CA"},
            ],
        )
        cubano.register("default", engine)

        result = Sales.query().metrics(Sales.revenue).execute()
        assert result[0].revenue == 1000
        assert result[1].revenue == 2000

    def test_execute_result_bool(self):
        """Result should be truthy if non-empty, falsy if empty."""
        import cubano

        engine_empty = MockEngine()
        cubano.register("empty_test", engine_empty)

        # Empty result
        result_empty = Sales.query().using("empty_test").metrics(Sales.revenue).execute()
        assert not result_empty

        # Non-empty result
        engine_filled = MockEngine()
        engine_filled.load("sales_view", [{"revenue": 1000}])
        cubano.register("filled_test", engine_filled)
        result_filled = Sales.query().using("filled_test").metrics(Sales.revenue).execute()
        assert result_filled


class TestModelCentricWorkflow:
    """Integration test demonstrating complete Phase 10.1 workflow."""

    def test_model_centric_workflow_complete(self):
        """
        Demonstrate complete workflow.

        - Model definition with introspection
        - Query via model.query()
        - Field operators for filtering
        - Eager execution with Result

        This test validates all LOCKED decisions:
        1. Model.query() as primary entry point
        2. Field operators returning Predicate objects
        3. Query.where() for Pythonic filtering
        4. Query.execute() for eager execution
        5. Result objects for result access.
        """
        import cubano

        # 1. Define model
        class Sales(SemanticView, view="sales"):
            revenue = Metric()
            users_count = Metric()
            region = Dimension()
            country = Dimension()

        # 2. Introspect fields
        metrics = Sales.metrics()
        assert len(metrics) == 2
        assert {m.name for m in metrics} == {"revenue", "users_count"}

        dims = Sales.dimensions()
        assert len(dims) == 2
        assert {d.name for d in dims} == {"region", "country"}

        # 3. Register engine with test data
        engine = MockEngine()
        engine.load(
            "sales",
            [
                {"revenue": 1000, "users_count": 10, "region": "West", "country": "US"},
                {"revenue": 2000, "users_count": 20, "region": "East", "country": "US"},
                {"revenue": 1500, "users_count": 15, "region": "West", "country": "CA"},
            ],
        )
        cubano.register("default", engine)

        # 4. Build query with field operators
        result = (
            Sales.query()
            .metrics(Sales.revenue, Sales.users_count)
            .dimensions(Sales.region)
            .where((Sales.country == "US") | (Sales.country == "CA"))
            .where(Sales.revenue > 500)
            .order_by(Sales.revenue.desc())
            .limit(10)
            .execute()
        )

        # 5. Verify Result object
        assert isinstance(result, Result)
        assert len(result) == 3

        # 6. Access rows
        for row in result:
            assert "revenue" in row._data
            assert "region" in row._data
            # Verify row access patterns
            _ = row.revenue
            _ = row["region"]


class TestQueryRepr:
    """Test _Query repr."""

    def test_bound_query_shows_model(self) -> None:
        """Model.query() repr should show model name."""
        q = Sales.query()
        repr_str = repr(q)
        assert "<Query" in repr_str
        assert "model=Sales" in repr_str

    def test_query_shows_metrics(self) -> None:
        """Query repr should list metric field names."""
        q = Sales.query().metrics(Sales.revenue, Sales.cost)
        repr_str = repr(q)
        assert "metrics=" in repr_str
        assert "'revenue'" in repr_str
        assert "'cost'" in repr_str

    def test_query_shows_dimensions(self) -> None:
        """Query repr should list dimension field names."""
        q = Sales.query().dimensions(Sales.country)
        repr_str = repr(q)
        assert "dimensions=" in repr_str
        assert "'country'" in repr_str

    def test_query_shows_limit(self) -> None:
        """Query repr should show limit value."""
        q = Sales.query().metrics(Sales.revenue).limit(10)
        assert "limit=10" in repr(q)

    def test_query_shows_where(self) -> None:
        """Query repr should show filter predicates."""
        q = Sales.query().where(Sales.country == "US")
        assert "where=" in repr(q)

    def test_query_shows_order_by(self) -> None:
        """Query repr should show order_by fields."""
        q = Sales.query().metrics(Sales.revenue).order_by(Sales.revenue.desc())
        repr_str = repr(q)
        assert "order_by=" in repr_str

    def test_query_shows_using(self) -> None:
        """Query repr should show engine binding."""
        q = Sales.query(using="warehouse")
        assert "using='warehouse'" in repr(q)

    def test_unbound_query_repr(self) -> None:
        """_Query() without model should show model=unbound."""
        q = _Query()
        repr_str = repr(q)
        assert "model=unbound" in repr_str

    def test_model_propagates_through_chain(self) -> None:
        """_model should propagate through all chained builder methods."""
        q = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
            .order_by(Sales.revenue.desc())
            .limit(10)
        )
        assert q._model is Sales
        assert "model=Sales" in repr(q)
