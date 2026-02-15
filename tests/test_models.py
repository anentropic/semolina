"""Tests for SemanticView model base class."""

import types

import pytest

from cubano import Dimension, Fact, Metric, SemanticView


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
