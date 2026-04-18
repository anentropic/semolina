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

from semolina import Dimension, Fact, Metric, SemanticView
from semolina.cursor import SemolinaCursor
from semolina.fields import NullsOrdering, OrderTerm
from semolina.filters import And, Exact, Gt, Or, Predicate
from semolina.pool import MockPool
from semolina.query import _Query


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
    """Test Query.using() method for per-query pool selection."""

    def test_using_returns_new_query(self):
        """using() should return new Query instance (immutability)."""
        q1 = _Query().metrics(Sales.revenue)
        q2 = q1.using("warehouse")
        assert q1 is not q2
        assert q1._using is None
        assert q2._using == "warehouse"

    def test_using_stores_engine_name(self):
        """using() should store pool name for lazy resolution."""
        q = _Query().metrics(Sales.revenue).using("my_engine")
        assert q._using == "my_engine"

    def test_using_with_non_string_raises(self):
        """using() should reject non-string arguments."""
        q = _Query().metrics(Sales.revenue)
        with pytest.raises(TypeError, match="requires pool name string"):
            q.using(123)
        with pytest.raises(TypeError, match="requires pool name string"):
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

    def test_fetch_returns_semolina_cursor(self):
        """execute() should return SemolinaCursor."""
        import semolina

        pool = MockPool()
        pool.load("sales_view", [{"revenue": 1000, "country": "US"}])
        semolina.register("default", pool, dialect="mock")

        cursor = _Query().metrics(Sales.revenue).execute()
        from semolina import Row

        assert isinstance(cursor, SemolinaCursor)
        rows = cursor.fetchall_rows()
        assert len(rows) == 1
        assert isinstance(rows[0], Row)
        cursor.close()

    def test_fetch_row_attribute_access(self):
        """Cursor rows should support attribute access."""
        import semolina

        pool = MockPool()
        pool.load("sales_view", [{"revenue": 1000, "country": "US"}])
        semolina.register("default", pool, dialect="mock")

        cursor = _Query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        rows = cursor.fetchall_rows()
        assert rows[0].revenue == 1000
        assert rows[0].country == "US"
        cursor.close()

    def test_fetch_row_dict_access(self):
        """Cursor rows should support dict-style access."""
        import semolina

        pool = MockPool()
        pool.load("sales_view", [{"revenue": 500, "country": "CA"}])
        semolina.register("default", pool, dialect="mock")

        cursor = _Query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        rows = cursor.fetchall_rows()
        assert rows[0]["revenue"] == 500
        assert rows[0]["country"] == "CA"
        cursor.close()

    def test_fetch_with_default_engine(self):
        """execute() without using() should use default pool."""
        import semolina

        pool = MockPool()
        pool.load("sales_view", [{"revenue": 1000}])
        semolina.register("default", pool, dialect="mock")

        cursor = _Query().metrics(Sales.revenue).execute()
        rows = cursor.fetchall_rows()
        assert len(rows) == 1
        assert rows[0].revenue == 1000
        cursor.close()

    def test_fetch_with_named_engine(self):
        """execute() with using() should use named pool."""
        import semolina

        pool = MockPool()
        pool.load("sales_view", [{"revenue": 2000}])
        semolina.register("warehouse", pool, dialect="mock")

        cursor = _Query().metrics(Sales.revenue).using("warehouse").execute()
        rows = cursor.fetchall_rows()
        assert len(rows) == 1
        assert rows[0].revenue == 2000
        cursor.close()

    def test_fetch_no_engine_raises(self):
        """execute() with no pool or engine registered should raise ValueError."""
        q = _Query().metrics(Sales.revenue)
        with pytest.raises(ValueError, match="No engine registered"):
            q.execute()

    def test_fetch_wrong_engine_name_raises(self):
        """execute() with non-existent pool name should raise ValueError."""
        import semolina

        pool = MockPool()
        semolina.register("default", pool, dialect="mock")

        q = _Query().metrics(Sales.revenue).using("other")
        with pytest.raises(ValueError, match="No engine registered with name 'other'"):
            q.execute()

    def test_fetch_empty_query_raises(self):
        """execute() on empty query should raise ValueError."""
        import semolina

        pool = MockPool()
        semolina.register("default", pool, dialect="mock")

        q = _Query()
        with pytest.raises(ValueError, match="must select at least one metric or dimension"):
            q.execute()

    def test_fetch_empty_fixtures(self):
        """execute() with no fixtures loaded should return empty cursor."""
        import semolina

        pool = MockPool()  # No fixtures loaded
        semolina.register("default", pool, dialect="mock")

        cursor = _Query().metrics(Sales.revenue).execute()
        rows = cursor.fetchall_rows()
        assert len(rows) == 0
        cursor.close()

    def test_fetch_lazy_resolution(self):
        """Pool should be resolved at execute() time, not during query construction."""
        import semolina

        # Create query BEFORE registering pool
        q = _Query().metrics(Sales.revenue).using("later")

        # Register pool AFTER query creation
        pool = MockPool()
        pool.load("sales_view", [{"revenue": 1500}])
        semolina.register("later", pool, dialect="mock")

        # execute() should succeed (proves lazy resolution)
        cursor = q.execute()
        rows = cursor.fetchall_rows()
        assert len(rows) == 1
        assert rows[0].revenue == 1500
        cursor.close()


class TestQueryFetchIntegration:
    """Integration tests for full query execution pipeline."""

    def test_full_pipeline(self):
        """Test complete pipeline: define model, build query, register pool, fetch results."""
        import semolina

        # Register pool with fixture data
        pool = MockPool()
        pool.load(
            "sales_view",
            [
                {"revenue": 1000, "cost": 100, "country": "US", "region": "West"},
                {"revenue": 2000, "cost": 200, "country": "CA", "region": "West"},
                {"revenue": 500, "cost": 50, "country": "US", "region": "East"},
            ],
        )
        semolina.register("default", pool, dialect="mock")

        # Build and execute query
        cursor = (
            _Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country)
            .limit(10)
            .execute()
        )

        # Verify Row objects with proper access patterns
        rows = cursor.fetchall_rows()
        assert len(rows) == 3
        assert rows[0].revenue == 1000
        assert rows[0]["cost"] == 100
        assert rows[1].country == "CA"
        cursor.close()

    def test_multiple_engines(self):
        """Should select correct pool based on using()."""
        import semolina

        # Register two pools with different data
        pool1 = MockPool()
        pool1.load("sales_view", [{"revenue": 1000}])
        semolina.register("engine1", pool1, dialect="mock")

        pool2 = MockPool()
        pool2.load("sales_view", [{"revenue": 9999}])
        semolina.register("engine2", pool2, dialect="mock")

        # Same query, different pools
        q = _Query().metrics(Sales.revenue)

        cursor1 = q.using("engine1").execute()
        rows1 = cursor1.fetchall_rows()
        assert rows1[0].revenue == 1000
        cursor1.close()

        cursor2 = q.using("engine2").execute()
        rows2 = cursor2.fetchall_rows()
        assert rows2[0].revenue == 9999
        cursor2.close()

    def test_query_reuse_with_different_engines(self):
        """Same query instance can be executed with different pools."""
        import semolina

        # Register two pools
        pool1 = MockPool()
        pool1.load("sales_view", [{"revenue": 100}])
        semolina.register("prod", pool1, dialect="mock")

        pool2 = MockPool()
        pool2.load("sales_view", [{"revenue": 200}])
        semolina.register("test", pool2, dialect="mock")

        # Create base query once
        base_query = _Query().metrics(Sales.revenue).dimensions(Sales.country)

        # Execute against different engines
        prod_cursor = base_query.using("prod").execute()
        prod_rows = prod_cursor.fetchall_rows()
        prod_cursor.close()

        test_cursor = base_query.using("test").execute()
        test_rows = test_cursor.fetchall_rows()
        test_cursor.close()

        assert prod_rows[0].revenue == 100
        assert test_rows[0].revenue == 200


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
        from semolina.filters import NotEqual

        pred = Sales.country != "US"
        assert isinstance(pred, NotEqual)
        assert pred.field_name == "country"
        assert pred.value == "US"

    def test_field_less_than_returns_lt(self):
        """Field < value should return Lt predicate."""
        from semolina.filters import Lt

        pred = Sales.revenue < 1000
        assert isinstance(pred, Lt)
        assert pred.field_name == "revenue"
        assert pred.value == 1000

    def test_field_less_equal_returns_lte(self):
        """Field <= value should return Lte predicate."""
        from semolina.filters import Lte

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
        from semolina.filters import Gte

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
    """Test Query.execute() for eager execution returning SemolinaCursor."""

    def test_execute_returns_semolina_cursor(self):
        """execute() should return SemolinaCursor, not list."""
        import semolina

        pool = MockPool()
        pool.load("sales_view", [{"revenue": 1000, "country": "US"}])
        semolina.register("default", pool, dialect="mock")

        cursor = Sales.query().metrics(Sales.revenue).execute()
        assert isinstance(cursor, SemolinaCursor)
        cursor.close()

    def test_execute_cursor_has_row_objects(self):
        """Cursor from execute() should provide Row objects via fetchall_rows."""
        import semolina

        pool = MockPool()
        pool.load(
            "sales_view",
            [
                {"revenue": 1000, "country": "US"},
                {"revenue": 2000, "country": "CA"},
            ],
        )
        semolina.register("default", pool, dialect="mock")

        cursor = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        rows = cursor.fetchall_rows()
        assert len(rows) == 2
        assert rows[0].revenue == 1000
        assert rows[1].country == "CA"
        cursor.close()

    def test_execute_rows_support_iteration(self):
        """Rows from cursor.fetchall_rows() should be iterable."""
        import semolina

        pool = MockPool()
        pool.load(
            "sales_view",
            [
                {"revenue": 1000, "country": "US"},
                {"revenue": 2000, "country": "CA"},
            ],
        )
        semolina.register("default", pool, dialect="mock")

        cursor = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).execute()
        rows = cursor.fetchall_rows()
        assert len(rows) == 2
        assert rows[0].revenue == 1000
        cursor.close()

    def test_execute_rows_support_indexing(self):
        """Rows from cursor.fetchall_rows() should support indexing."""
        import semolina

        pool = MockPool()
        pool.load(
            "sales_view",
            [
                {"revenue": 1000, "country": "US"},
                {"revenue": 2000, "country": "CA"},
            ],
        )
        semolina.register("default", pool, dialect="mock")

        cursor = Sales.query().metrics(Sales.revenue).execute()
        rows = cursor.fetchall_rows()
        assert rows[0].revenue == 1000
        assert rows[1].revenue == 2000
        cursor.close()

    def test_execute_empty_vs_nonempty(self):
        """fetchall_rows() returns empty list for no data, non-empty for data."""
        import semolina

        pool_empty = MockPool()
        semolina.register("empty_test", pool_empty, dialect="mock")

        # Empty result
        cursor_empty = Sales.query().using("empty_test").metrics(Sales.revenue).execute()
        rows_empty = cursor_empty.fetchall_rows()
        assert len(rows_empty) == 0
        cursor_empty.close()

        # Non-empty result
        pool_filled = MockPool()
        pool_filled.load("sales_view", [{"revenue": 1000}])
        semolina.register("filled_test", pool_filled, dialect="mock")
        cursor_filled = Sales.query().using("filled_test").metrics(Sales.revenue).execute()
        rows_filled = cursor_filled.fetchall_rows()
        assert len(rows_filled) == 1
        cursor_filled.close()


class TestModelCentricWorkflow:
    """Integration test demonstrating complete Phase 10.1 workflow."""

    def test_model_centric_workflow_complete(self):
        """
        Demonstrate complete workflow.

        - Model definition with introspection
        - Query via model.query()
        - Field operators for filtering
        - Eager execution with SemolinaCursor

        This test validates all LOCKED decisions:
        1. Model.query() as primary entry point
        2. Field operators returning Predicate objects
        3. Query.where() for Pythonic filtering
        4. Query.execute() for eager execution
        5. SemolinaCursor for result access.
        """
        import semolina

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

        # 3. Register pool with test data
        pool = MockPool()
        pool.load(
            "sales",
            [
                {"revenue": 1000, "users_count": 10, "region": "West", "country": "US"},
                {"revenue": 2000, "users_count": 20, "region": "East", "country": "US"},
                {"revenue": 1500, "users_count": 15, "region": "West", "country": "CA"},
            ],
        )
        semolina.register("default", pool, dialect="mock")

        # 4. Build query with field operators
        cursor = (
            Sales.query()
            .metrics(Sales.revenue, Sales.users_count)
            .dimensions(Sales.region)
            .where((Sales.country == "US") | (Sales.country == "CA"))
            .where(Sales.revenue > 500)
            .order_by(Sales.revenue.desc())
            .limit(10)
            .execute()
        )

        # 5. Verify SemolinaCursor
        assert isinstance(cursor, SemolinaCursor)
        rows = cursor.fetchall_rows()
        assert len(rows) == 3

        # 6. Access rows
        for row in rows:
            assert "revenue" in row._data
            assert "region" in row._data
            # Verify row access patterns
            _ = row.revenue
            _ = row["region"]
        cursor.close()


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


class TestQueryShorthand:
    """Test query(metrics=..., dimensions=...) shorthand (QAPI-01)."""

    def test_shorthand_metrics_only(self) -> None:
        """Sales.query(metrics=[Sales.revenue]) should produce _Query with _metrics set."""
        q = Sales.query(metrics=[Sales.revenue])
        assert q._metrics == (Sales.revenue,)
        assert q._dimensions == ()

    def test_shorthand_dimensions_only(self) -> None:
        """Sales.query(dimensions=[Sales.region]) should produce _Query with _dimensions set."""
        q = Sales.query(dimensions=[Sales.region])
        assert q._dimensions == (Sales.region,)
        assert q._metrics == ()

    def test_shorthand_both(self) -> None:
        """Sales.query(metrics=..., dimensions=...) should set both."""
        q = Sales.query(metrics=[Sales.revenue], dimensions=[Sales.region])
        assert q._metrics == (Sales.revenue,)
        assert q._dimensions == (Sales.region,)

    def test_shorthand_multiple_metrics(self) -> None:
        """Sales.query(metrics=[Sales.revenue, Sales.cost]) should set both metrics."""
        q = Sales.query(metrics=[Sales.revenue, Sales.cost])
        assert q._metrics == (Sales.revenue, Sales.cost)

    def test_shorthand_with_using(self) -> None:
        """Sales.query(metrics=..., using=...) should set both _metrics and _using."""
        q = Sales.query(metrics=[Sales.revenue], using="warehouse")
        assert q._metrics == (Sales.revenue,)
        assert q._using == "warehouse"

    def test_shorthand_equivalent_to_builder(self) -> None:
        """Shorthand and builder chain should produce identical _metrics and _dimensions."""
        q_shorthand = Sales.query(metrics=[Sales.revenue], dimensions=[Sales.region])
        q_builder = Sales.query().metrics(Sales.revenue).dimensions(Sales.region)
        assert q_shorthand._metrics == q_builder._metrics
        assert q_shorthand._dimensions == q_builder._dimensions

    def test_shorthand_empty_list_noop(self) -> None:
        """Sales.query(metrics=[]) should produce empty _metrics (no error)."""
        q = Sales.query(metrics=[])
        assert q._metrics == ()

    def test_shorthand_none_noop(self) -> None:
        """Sales.query(metrics=None) should produce empty _metrics (no error)."""
        q = Sales.query(metrics=None)
        assert q._metrics == ()

    def test_shorthand_rejects_dimension_as_metric(self) -> None:
        """Sales.query(metrics=[Sales.region]) should raise TypeError."""
        with pytest.raises(TypeError, match="Did you mean .dimensions()"):
            Sales.query(metrics=[Sales.region])  # type: ignore[reportArgumentType]

    def test_shorthand_rejects_metric_as_dimension(self) -> None:
        """Sales.query(dimensions=[Sales.revenue]) should raise TypeError."""
        with pytest.raises(TypeError, match="Did you mean .metrics()"):
            Sales.query(dimensions=[Sales.revenue])  # type: ignore[reportArgumentType]

    def test_shorthand_rejects_cross_model_field(self) -> None:
        """Sales.query(metrics=[OtherModel.some_metric]) should raise TypeError."""

        class Other(SemanticView, view="other"):
            some_metric = Metric()

        with pytest.raises(TypeError, match="Cannot mix fields from different models"):
            Sales.query(metrics=[Other.some_metric])

    def test_shorthand_fact_in_dimensions(self) -> None:
        """Sales.query(dimensions=[Sales.unit_price]) should accept Fact fields."""
        q = Sales.query(dimensions=[Sales.unit_price])
        assert q._dimensions == (Sales.unit_price,)

    def test_shorthand_keyword_only(self) -> None:
        """Sales.query([Sales.revenue]) should raise TypeError (positional not allowed)."""
        with pytest.raises(TypeError):
            Sales.query([Sales.revenue])  # type: ignore[call-arg]


class TestQueryShorthandAdditivity:
    """Test builder methods additive with shorthand args (QAPI-02)."""

    def test_additive_metrics(self) -> None:
        """Shorthand metrics + builder .metrics() should be additive."""
        q = Sales.query(metrics=[Sales.revenue]).metrics(Sales.cost)
        assert q._metrics == (Sales.revenue, Sales.cost)

    def test_additive_dimensions(self) -> None:
        """Shorthand dimensions + builder .dimensions() should be additive."""
        q = Sales.query(dimensions=[Sales.region]).dimensions(Sales.country)
        assert q._dimensions == (Sales.region, Sales.country)

    def test_additive_mixed(self) -> None:
        """Shorthand metrics + builder .metrics() + .dimensions() should all be additive."""
        q = Sales.query(metrics=[Sales.revenue]).metrics(Sales.cost).dimensions(Sales.region)
        assert q._metrics == (Sales.revenue, Sales.cost)
        assert q._dimensions == (Sales.region,)

    def test_shorthand_sql_output(self) -> None:
        """Shorthand query .to_sql() should produce valid SQL."""
        sql = Sales.query(metrics=[Sales.revenue], dimensions=[Sales.region]).to_sql()
        assert "AGG" in sql
        assert "region" in sql.lower()
