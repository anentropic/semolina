"""
Tests for Query builder with immutability and method chaining.

Tests cover:
- QRY-01: .metrics() accepts Metric fields only
- QRY-02: .dimensions() accepts Dimension fields
- QRY-03: .dimensions() accepts Fact fields
- QRY-04: .filter() accepts Q objects and combines with AND
- QRY-05: .order_by() accepts Field instances
- QRY-06: .limit() accepts positive integers
- QRY-07: Query immutability (frozen dataclass)
- QRY-08: Method chaining returns new instances
"""

import pytest

from cubano import Dimension, Fact, Metric, SemanticView
from cubano.fields import NullsOrdering, OrderTerm
from cubano.filters import Q
from cubano.query import Query


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
        q = Query().metrics(Sales.revenue)
        assert q._metrics == (Sales.revenue,)

    def test_metrics_multiple_fields(self):
        """Should accept multiple Metric fields."""
        q = Query().metrics(Sales.revenue, Sales.cost)
        assert q._metrics == (Sales.revenue, Sales.cost)

    def test_metrics_rejects_dimension(self):
        """Should reject Dimension fields with helpful error."""
        with pytest.raises(TypeError) as exc_info:
            Query().metrics(Sales.country)
        assert "Did you mean .dimensions()?" in str(exc_info.value)

    def test_metrics_rejects_fact(self):
        """Should reject Fact fields with helpful error."""
        with pytest.raises(TypeError) as exc_info:
            Query().metrics(Sales.unit_price)
        assert "Did you mean .dimensions()?" in str(exc_info.value)

    def test_metrics_empty_raises_error(self):
        """Should reject empty call."""
        with pytest.raises(ValueError) as exc_info:
            Query().metrics()
        assert "At least one metric" in str(exc_info.value)

    def test_metrics_accumulates(self):
        """Multiple .metrics() calls should accumulate, not replace."""
        q = Query().metrics(Sales.revenue).metrics(Sales.cost)
        assert q._metrics == (Sales.revenue, Sales.cost)


class TestQueryDimensions:
    """Test .dimensions() method (QRY-02, QRY-03)."""

    def test_dimensions_single_dimension(self):
        """Should accept single Dimension field."""
        q = Query().dimensions(Sales.country)
        assert q._dimensions == (Sales.country,)

    def test_dimensions_multiple_dimensions(self):
        """Should accept multiple Dimension fields."""
        q = Query().dimensions(Sales.country, Sales.region)
        assert q._dimensions == (Sales.country, Sales.region)

    def test_dimensions_accepts_fact(self):
        """Should accept Fact fields (QRY-03)."""
        q = Query().dimensions(Sales.unit_price)
        assert q._dimensions == (Sales.unit_price,)

    def test_dimensions_mixed_dimension_and_fact(self):
        """Should accept both Dimension and Fact together."""
        q = Query().dimensions(Sales.country, Sales.unit_price)
        assert q._dimensions == (Sales.country, Sales.unit_price)

    def test_dimensions_rejects_metric(self):
        """Should reject Metric fields with helpful error."""
        with pytest.raises(TypeError) as exc_info:
            Query().dimensions(Sales.revenue)
        assert "Did you mean .metrics()?" in str(exc_info.value)

    def test_dimensions_empty_raises_error(self):
        """Should reject empty call."""
        with pytest.raises(ValueError) as exc_info:
            Query().dimensions()
        assert "At least one dimension" in str(exc_info.value)

    def test_dimensions_accumulates(self):
        """Multiple .dimensions() calls should accumulate, not replace."""
        q = Query().dimensions(Sales.country).dimensions(Sales.region)
        assert q._dimensions == (Sales.country, Sales.region)


class TestQueryFilter:
    """Test .filter() method (QRY-04)."""

    def test_filter_single_q_object(self):
        """Should accept Q object."""
        q = Query().filter(Q(country="US"))
        assert q._filters is not None
        assert isinstance(q._filters, Q)

    def test_filter_combines_with_and(self):
        """Multiple .filter() calls should AND together."""
        q1 = Query().filter(Q(country="US"))
        q2 = q1.filter(Q(region="West"))

        # Should be combined with AND
        assert q2._filters is not None
        assert q2._filters.connector == Q.AND
        # Should have both conditions as children
        assert len(q2._filters.children) == 2

    def test_filter_rejects_non_q(self):
        """Should reject non-Q objects."""
        with pytest.raises(TypeError) as exc_info:
            Query().filter("country=US")
        assert "requires Q object" in str(exc_info.value)


class TestQueryOrderBy:
    """Test .order_by() method (QRY-05)."""

    def test_order_by_single_field(self):
        """Should accept single Field."""
        q = Query().order_by(Sales.revenue)
        assert q._order_by_fields == (Sales.revenue,)

    def test_order_by_multiple_fields(self):
        """Should accept multiple Fields."""
        q = Query().order_by(Sales.revenue, Sales.country)
        assert q._order_by_fields == (Sales.revenue, Sales.country)

    def test_order_by_accepts_any_field_type(self):
        """Should accept Metric, Dimension, or Fact."""
        q = Query().order_by(Sales.revenue, Sales.country, Sales.unit_price)
        assert q._order_by_fields == (Sales.revenue, Sales.country, Sales.unit_price)

    def test_order_by_rejects_non_field(self):
        """Should reject non-Field objects."""
        with pytest.raises(TypeError) as exc_info:
            Query().order_by("revenue")
        assert "requires Field" in str(exc_info.value)

    def test_order_by_empty_raises_error(self):
        """Should reject empty call."""
        with pytest.raises(ValueError) as exc_info:
            Query().order_by()
        assert "At least one field" in str(exc_info.value)

    def test_order_by_accumulates(self):
        """Multiple .order_by() calls should accumulate, not replace."""
        q = Query().order_by(Sales.revenue).order_by(Sales.country)
        assert q._order_by_fields == (Sales.revenue, Sales.country)

    def test_order_by_descending(self):
        """Query().order_by(Sales.revenue.desc()) should store OrderTerm."""
        q = Query().order_by(Sales.revenue.desc())
        assert len(q._order_by_fields) == 1
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert q._order_by_fields[0].field is Sales.revenue
        assert q._order_by_fields[0].descending is True

    def test_order_by_ascending_explicit(self):
        """Query().order_by(Sales.revenue.asc()) should store OrderTerm."""
        q = Query().order_by(Sales.revenue.asc())
        assert len(q._order_by_fields) == 1
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert q._order_by_fields[0].field is Sales.revenue
        assert q._order_by_fields[0].descending is False

    def test_order_by_with_nulls_first(self):
        """Query().order_by() with desc(NullsOrdering.FIRST) stores nulls=FIRST."""
        q = Query().order_by(Sales.revenue.desc(NullsOrdering.FIRST))
        assert len(q._order_by_fields) == 1
        term = q._order_by_fields[0]
        assert isinstance(term, OrderTerm)
        assert term.nulls == NullsOrdering.FIRST

    def test_order_by_with_nulls_last(self):
        """Query().order_by() with asc(NullsOrdering.LAST) stores nulls=LAST."""
        q = Query().order_by(Sales.revenue.asc(NullsOrdering.LAST))
        assert len(q._order_by_fields) == 1
        term = q._order_by_fields[0]
        assert isinstance(term, OrderTerm)
        assert term.nulls == NullsOrdering.LAST

    def test_order_by_mixed_directions(self):
        """Query().order_by() with desc() and asc() stores both OrderTerms."""
        q = Query().order_by(Sales.revenue.desc(), Sales.country.asc())
        assert len(q._order_by_fields) == 2
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert isinstance(q._order_by_fields[1], OrderTerm)
        assert q._order_by_fields[0].descending is True
        assert q._order_by_fields[1].descending is False

    def test_order_by_mixed_nulls_handling(self):
        """Query().order_by() with mixed NULLS FIRST/LAST stores both correctly."""
        q = Query().order_by(
            Sales.revenue.desc(NullsOrdering.FIRST), Sales.country.asc(NullsOrdering.LAST)
        )
        assert len(q._order_by_fields) == 2
        assert q._order_by_fields[0].nulls == NullsOrdering.FIRST
        assert q._order_by_fields[1].nulls == NullsOrdering.LAST

    def test_order_by_bare_field_still_works(self):
        """Query().order_by(Sales.revenue) continues to work (backward compatible)."""
        q = Query().order_by(Sales.revenue)
        assert q._order_by_fields == (Sales.revenue,)
        # Bare field stored as-is, not wrapped in OrderTerm
        assert isinstance(q._order_by_fields[0], Metric)

    def test_order_by_mixed_field_and_order_term(self):
        """Query().order_by() accepts mix of OrderTerm and bare Field."""
        q = Query().order_by(Sales.revenue.desc(), Sales.country)
        assert len(q._order_by_fields) == 2
        assert isinstance(q._order_by_fields[0], OrderTerm)
        assert isinstance(q._order_by_fields[1], Dimension)


class TestQueryLimit:
    """Test .limit() method (QRY-06)."""

    def test_limit_positive_integer(self):
        """Should accept positive integers."""
        q = Query().limit(100)
        assert q._limit_value == 100

    def test_limit_rejects_zero(self):
        """Should reject zero."""
        with pytest.raises(ValueError) as exc_info:
            Query().limit(0)
        assert "positive integer" in str(exc_info.value)

    def test_limit_rejects_negative(self):
        """Should reject negative values."""
        with pytest.raises(ValueError) as exc_info:
            Query().limit(-10)
        assert "positive integer" in str(exc_info.value)

    def test_limit_rejects_float(self):
        """Should reject float values."""
        with pytest.raises(TypeError) as exc_info:
            Query().limit(3.14)
        assert "requires int" in str(exc_info.value)


class TestQueryImmutability:
    """Test Query immutability (QRY-07)."""

    def test_query_is_frozen(self):
        """Query should be a frozen dataclass."""
        q = Query()
        # Attempt to modify should raise (frozen dataclass raises FrozenInstanceError)
        with pytest.raises((AttributeError, TypeError)):
            q._metrics = (Sales.revenue,)  # type: ignore[misc]

    def test_metrics_returns_new_instance(self):
        """metrics() should return new instance, original unchanged."""
        q1 = Query()
        q2 = q1.metrics(Sales.revenue)

        assert q1._metrics == ()
        assert q2._metrics == (Sales.revenue,)
        assert q1 is not q2

    def test_dimensions_returns_new_instance(self):
        """dimensions() should return new instance, original unchanged."""
        q1 = Query()
        q2 = q1.dimensions(Sales.country)

        assert q1._dimensions == ()
        assert q2._dimensions == (Sales.country,)
        assert q1 is not q2

    def test_filter_returns_new_instance(self):
        """filter() should return new instance, original unchanged."""
        q1 = Query()
        q2 = q1.filter(Q(country="US"))

        assert q1._filters is None
        assert q2._filters is not None
        assert q1 is not q2

    def test_order_by_returns_new_instance(self):
        """order_by() should return new instance, original unchanged."""
        q1 = Query()
        q2 = q1.order_by(Sales.revenue)

        assert q1._order_by_fields == ()
        assert q2._order_by_fields == (Sales.revenue,)
        assert q1 is not q2

    def test_limit_returns_new_instance(self):
        """limit() should return new instance, original unchanged."""
        q1 = Query()
        q2 = q1.limit(100)

        assert q1._limit_value is None
        assert q2._limit_value == 100
        assert q1 is not q2


class TestQueryChaining:
    """Test method chaining (QRY-08)."""

    def test_full_method_chain(self):
        """Should support full method chain."""
        q = (
            Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country, Sales.region)
            .filter(Q(country="US") | Q(country="CA"))
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
        base = Query().metrics(Sales.revenue)
        with_dims = base.dimensions(Sales.country)
        filtered = with_dims.filter(Q(country="US"))

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
            Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country)
            .filter(Q(country="US"))
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
        q = Query()
        with pytest.raises(ValueError) as exc_info:
            q._validate_for_execution()
        assert "at least one metric or dimension" in str(exc_info.value)

    def test_query_with_metrics_validates(self):
        """Query with metrics should pass validation."""
        q = Query().metrics(Sales.revenue)
        # Should not raise
        q._validate_for_execution()

    def test_query_with_dimensions_validates(self):
        """Query with dimensions should pass validation."""
        q = Query().dimensions(Sales.country)
        # Should not raise
        q._validate_for_execution()

    def test_query_with_both_validates(self):
        """Query with both metrics and dimensions should pass validation."""
        q = Query().metrics(Sales.revenue).dimensions(Sales.country)
        # Should not raise
        q._validate_for_execution()


class TestQueryStubs:
    """Test stub methods for future phases."""

    def test_to_sql_validates_then_raises(self):
        """to_sql() should validate, then raise NotImplementedError."""
        # Empty query should fail validation first
        q_empty = Query()
        with pytest.raises(ValueError):
            q_empty.to_sql()

        # Valid query should hit NotImplementedError
        q_valid = Query().metrics(Sales.revenue)
        with pytest.raises(NotImplementedError) as exc_info:
            q_valid.to_sql()
        assert "Phase 3" in str(exc_info.value) or "SQL generation" in str(exc_info.value)

    def test_fetch_validates_then_raises(self):
        """fetch() should validate, then raise NotImplementedError."""
        # Empty query should fail validation first
        q_empty = Query()
        with pytest.raises(ValueError):
            q_empty.fetch()

        # Valid query should hit NotImplementedError
        q_valid = Query().metrics(Sales.revenue)
        with pytest.raises(NotImplementedError) as exc_info:
            q_valid.fetch()
        assert "Phase 4" in str(exc_info.value) or "execution" in str(exc_info.value)
