"""
Tests for SemanticView model base class.

Tests cover Phase 10.1 model-centric query API:
- Model.query() entry point for fluent API
- Model.metrics() and Model.dimensions() for introspection
- Reserved field names validation
"""

import types

import pytest

from cubano import Dimension, Fact, Metric, SemanticView
from cubano.query import _Query


class TestModelDefinition:
    """Test MOD-01: Model definition with view parameter."""

    def test_model_definition_with_view_parameter(self):
        """Should define model using SemanticView base with view parameter."""

        class Sales(SemanticView, view="sales"):
            pass

        assert Sales._view_name == "sales"

    def test_model_definition_requires_view_parameter(self):
        """Should raise TypeError when view parameter is missing."""

        with pytest.raises(TypeError, match="must specify a view parameter"):

            class InvalidModel(SemanticView):  # pyright: ignore[reportUnusedClass]
                pass

    def test_model_definition_with_empty_view(self):
        """Should accept empty string as view name."""

        class EmptyView(SemanticView, view=""):
            pass

        assert EmptyView._view_name == ""


class TestMetricFields:
    """Test MOD-02: Metric field declaration and access."""

    def test_declare_metric_field(self):
        """Should declare Metric fields with class-level syntax."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        assert hasattr(Sales, "revenue")
        assert isinstance(Sales.revenue, Metric)

    def test_metric_field_reference(self):
        """Should reference Metric field as Python attribute."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        revenue_field = Sales.revenue
        assert isinstance(revenue_field, Metric)
        assert revenue_field.name == "revenue"


class TestDimensionFields:
    """Test MOD-03: Dimension field declaration and access."""

    def test_declare_dimension_field(self):
        """Should declare Dimension fields with class-level syntax."""

        class Sales(SemanticView, view="sales"):
            country = Dimension()

        assert hasattr(Sales, "country")
        assert isinstance(Sales.country, Dimension)

    def test_dimension_field_reference(self):
        """Should reference Dimension field as Python attribute."""

        class Sales(SemanticView, view="sales"):
            country = Dimension()

        country_field = Sales.country
        assert isinstance(country_field, Dimension)
        assert country_field.name == "country"


class TestFactFields:
    """Test MOD-04: Fact field declaration and access."""

    def test_declare_fact_field(self):
        """Should declare Fact fields with class-level syntax."""

        class Sales(SemanticView, view="sales"):
            unit_price = Fact()

        assert hasattr(Sales, "unit_price")
        assert isinstance(Sales.unit_price, Fact)

    def test_fact_field_reference(self):
        """Should reference Fact field as Python attribute."""

        class Sales(SemanticView, view="sales"):
            unit_price = Fact()

        price_field = Sales.unit_price
        assert isinstance(price_field, Fact)
        assert price_field.name == "unit_price"


class TestFieldReferences:
    """Test MOD-05: Field reference as Python attributes returning Field instances."""

    def test_field_reference_returns_field_instance(self):
        """Field reference should return Field instance with correct name."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()
            country = Dimension()
            unit_price = Fact()

        # Test all field types
        revenue_field = Sales.revenue
        assert isinstance(revenue_field, Metric)
        assert revenue_field.name == "revenue"

        country_field = Sales.country
        assert isinstance(country_field, Dimension)
        assert country_field.name == "country"

        price_field = Sales.unit_price
        assert isinstance(price_field, Fact)
        assert price_field.name == "unit_price"


class TestMetadataCollection:
    """Test metadata collection and accessibility."""

    def test_view_name_metadata(self):
        """_view_name should be accessible and correct."""

        class Sales(SemanticView, view="sales_view"):
            revenue = Metric()

        assert Sales._view_name == "sales_view"

    def test_fields_metadata_collection(self):
        """_fields should contain all Field descriptors."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()
            country = Dimension()
            unit_price = Fact()

        assert len(Sales._fields) == 3
        assert "revenue" in Sales._fields
        assert "country" in Sales._fields
        assert "unit_price" in Sales._fields

        assert isinstance(Sales._fields["revenue"], Metric)
        assert isinstance(Sales._fields["country"], Dimension)
        assert isinstance(Sales._fields["unit_price"], Fact)

    def test_fields_is_immutable_mapping(self):
        """_fields should be a MappingProxyType (immutable)."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        assert isinstance(Sales._fields, types.MappingProxyType)

        # Should not be able to modify
        with pytest.raises(TypeError):
            Sales._fields["new_field"] = Metric()  # type: ignore


class TestModelFreezing:
    """Test metadata freezing - models are immutable after creation."""

    def test_cannot_modify_fields_after_creation(self):
        """Should raise AttributeError when trying to add fields after creation."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        with pytest.raises(AttributeError, match="Cannot modify.*after class creation"):
            Sales.new_field = Metric()

    def test_cannot_modify_metadata_after_creation(self):
        """Should raise AttributeError when trying to modify metadata."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        with pytest.raises(AttributeError, match="Cannot modify.*after class creation"):
            Sales._view_name = "new_view"

        with pytest.raises(AttributeError, match="Cannot modify.*after class creation"):
            Sales._frozen = False


class TestMultipleModels:
    """Test that multiple models don't share state."""

    def test_multiple_models_have_separate_metadata(self):
        """Multiple models should have independent metadata."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        class Products(SemanticView, view="products"):
            price = Metric()
            category = Dimension()

        # Check view names are separate
        assert Sales._view_name == "sales"
        assert Products._view_name == "products"

        # Check fields are separate
        assert len(Sales._fields) == 1
        assert len(Products._fields) == 2
        assert "revenue" in Sales._fields
        assert "revenue" not in Products._fields
        assert "price" in Products._fields
        assert "price" not in Sales._fields


class TestModelQuery:
    """Test Model.query() entry point for Phase 10.1 model-centric API."""

    def test_query_returns_query_instance(self):
        """Model.query() should return Query instance bound to model."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        q = Sales.query()
        assert isinstance(q, _Query)
        assert q._model is Sales

    def test_query_with_using_parameter(self):
        """Model.query(using='name') should set engine name."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        q = Sales.query(using="warehouse")
        assert q._using == "warehouse"
        assert q._model is Sales

    def test_query_enables_model_centric_chaining(self):
        """Model.query() enables fluent method chaining with field validation."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()
            country = Dimension()

        q = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)
        assert len(q._metrics) == 1
        assert len(q._dimensions) == 1

    def test_query_with_where_filter(self):
        """Model.query() works with .where() for Pythonic filtering."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()
            country = Dimension()

        # Field operators return Q objects
        q = Sales.query().where(Sales.country == "US")
        assert q._filters is not None

    def test_query_with_operator_composition(self):
        """Model.query().where() accepts composed field operators."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()
            country = Dimension()

        # OR composition
        from cubano.filters import Or

        q = Sales.query().where((Sales.country == "US") | (Sales.country == "CA"))
        assert q._filters is not None
        assert isinstance(q._filters, Or)


class TestModelIntrospection:
    """Test Model.metrics() and Model.dimensions() introspection methods."""

    def test_metrics_returns_list_of_metrics(self):
        """Model.metrics() returns all Metric fields."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()
            cost = Metric()
            country = Dimension()

        metrics = Sales.metrics()
        assert isinstance(metrics, list)
        assert len(metrics) == 2
        assert all(isinstance(m, Metric) for m in metrics)
        assert {m.name for m in metrics} == {"revenue", "cost"}

    def test_metrics_returns_empty_list_if_no_metrics(self):
        """Model.metrics() returns empty list if no Metric fields."""

        class Locations(SemanticView, view="locations"):
            country = Dimension()
            region = Dimension()

        metrics = Locations.metrics()
        assert metrics == []

    def test_dimensions_returns_dimensions_and_facts(self):
        """Model.dimensions() returns all Dimension and Fact fields."""

        class Orders(SemanticView, view="orders"):
            revenue = Metric()
            region = Dimension()
            date = Fact()

        dims = Orders.dimensions()
        assert isinstance(dims, list)
        assert len(dims) == 2
        assert all(isinstance(d, Dimension | Fact) for d in dims)
        assert {d.name for d in dims} == {"region", "date"}

    def test_dimensions_returns_empty_list_if_no_dimensions(self):
        """Model.dimensions() returns empty list if no Dimension/Fact fields."""

        class Metrics(SemanticView, view="metrics"):
            revenue = Metric()
            cost = Metric()

        dims = Metrics.dimensions()
        assert dims == []

    def test_introspection_returns_fields_with_metadata(self):
        """Introspection methods return Field objects with .name property."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()
            country = Dimension()

        metrics = Sales.metrics()
        assert metrics[0].name == "revenue"

        dims = Sales.dimensions()
        assert dims[0].name == "country"


class TestReservedFieldNames:
    """Test that reserved method names are rejected in field definitions."""

    def test_reserved_name_query_raises_error(self):
        """Field named 'query' should raise ValueError (Phase 10.1 reserved)."""

        with pytest.raises(ValueError, match="reserved"):

            class Invalid(SemanticView, view="invalid"):  # type: ignore[reportUnusedClass, assignment]  # noqa: F841
                query = Metric()  # type: ignore[assignment]  # 'query' is reserved

    def test_reserved_name_metrics_raises_error(self):
        """Field named 'metrics' should raise ValueError (Phase 10.1 reserved)."""

        with pytest.raises(ValueError, match="reserved"):

            class Invalid(SemanticView, view="invalid"):  # type: ignore[reportUnusedClass, assignment]  # noqa: F841
                metrics = Metric()  # type: ignore[assignment]  # 'metrics' is reserved

    def test_reserved_name_dimensions_raises_error(self):
        """Field named 'dimensions' should raise ValueError (Phase 10.1 reserved)."""

        with pytest.raises(ValueError, match="reserved"):

            class Invalid(SemanticView, view="invalid"):  # type: ignore[reportUnusedClass, assignment]  # noqa: F841
                dimensions = Metric()  # type: ignore[assignment]  # 'dimensions' is reserved

    def test_reserved_name_where_raises_error(self):
        """Field named 'where' should raise ValueError (Phase 10.1 reserved)."""

        with pytest.raises(ValueError, match="reserved"):

            class Invalid(SemanticView, view="invalid"):  # type: ignore[reportUnusedClass, assignment]  # noqa: F841
                where = Metric()  # type: ignore[assignment]  # 'where' is reserved

    def test_reserved_name_execute_raises_error(self):
        """Field named 'execute' should raise ValueError (Phase 10.1 reserved)."""

        with pytest.raises(ValueError, match="reserved"):

            class Invalid(SemanticView, view="invalid"):  # type: ignore[reportUnusedClass, assignment]  # noqa: F841
                execute = Metric()  # type: ignore[assignment]  # 'execute' is reserved

    def test_error_message_lists_alternatives(self):
        """Reserved name error should suggest alternatives."""

        with pytest.raises(ValueError) as exc_info:

            class Invalid(SemanticView, view="invalid"):  # type: ignore[reportUnusedClass, assignment]  # noqa: F841
                query = Metric()  # type: ignore[assignment]

        error_msg = str(exc_info.value)
        assert "query" in error_msg.lower()
        assert "reserved" in error_msg.lower()


class TestSemanticViewRepr:
    """Test SemanticView class repr via metaclass."""

    def test_subclass_repr_shows_view_name(self) -> None:
        """SemanticView subclass repr should include view name."""

        class Sales(SemanticView, view="sales_view"):
            revenue = Metric()
            country = Dimension()

        repr_str = repr(Sales)
        assert "SemanticView" in repr_str
        assert "'Sales'" in repr_str
        assert "sales_view" in repr_str

    def test_subclass_repr_shows_metrics(self) -> None:
        """SemanticView subclass repr should list metric field names."""

        class Sales(SemanticView, view="sales_view"):
            revenue = Metric()
            cost = Metric()
            country = Dimension()

        repr_str = repr(Sales)
        assert "metrics=" in repr_str
        assert "'revenue'" in repr_str
        assert "'cost'" in repr_str

    def test_subclass_repr_shows_dimensions(self) -> None:
        """SemanticView subclass repr should list dimension field names."""

        class Sales(SemanticView, view="sales_view"):
            revenue = Metric()
            country = Dimension()

        repr_str = repr(Sales)
        assert "dimensions=" in repr_str
        assert "'country'" in repr_str

    def test_subclass_repr_shows_facts(self) -> None:
        """SemanticView subclass repr should list fact field names."""

        class Sales(SemanticView, view="sales_view"):
            unit_price = Fact()

        repr_str = repr(Sales)
        assert "facts=" in repr_str
        assert "'unit_price'" in repr_str

    def test_subclass_repr_omits_empty_categories(self) -> None:
        """SemanticView repr should omit empty field categories."""

        class MetricsOnly(SemanticView, view="mo"):
            revenue = Metric()

        repr_str = repr(MetricsOnly)
        assert "dimensions=" not in repr_str
        assert "facts=" not in repr_str

    def test_base_class_repr_does_not_crash(self) -> None:
        """repr(SemanticView) should not crash (base class has no _view_name)."""
        repr_str = repr(SemanticView)
        assert isinstance(repr_str, str)
