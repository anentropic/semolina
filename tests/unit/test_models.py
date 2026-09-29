"""
Tests for the SemanticView model base class.

A model is observed the way a user observes it: the fields it exposes, what ``metrics()`` and
``dimensions()`` return, the SQL its queries render (which is where the view name shows up),
its ``repr``, and the errors a bad definition raises. Query building itself is tested in
``test_query.py``.
"""

import pytest

from semolina import Dimension, Fact, Metric, SemanticView
from semolina.fields import Field


class TestModelDefinition:
    """A model names its view with the ``view=`` class keyword."""

    def test_the_view_parameter_names_the_view_queried(self):
        """``view="sales"`` is the relation every query of the model reads from."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        assert (
            Sales.query().metrics(Sales.revenue).to_sql() == 'SELECT AGG("REVENUE")\nFROM "SALES"'
        )

    def test_model_definition_requires_view_parameter(self):
        """A model without ``view=`` is refused at class creation."""
        with pytest.raises(TypeError, match="must specify a view parameter"):

            class InvalidModel(SemanticView):  # pyright: ignore[reportUnusedClass]
                pass

    def test_model_definition_with_empty_view(self):
        """
        An empty view name is accepted today, and renders an empty identifier.

        Pinned as current behaviour, not endorsed: whether an empty view name should be
        refused at class creation is an open decision, and the day it is refused this test is
        the one to change.
        """

        class EmptyView(SemanticView, view=""):
            revenue = Metric()

        assert EmptyView.query().metrics(EmptyView.revenue).to_sql().endswith('\nFROM ""')


class TestFieldDeclaration:
    """Each field class declares a field of its own kind, named after its attribute."""

    @pytest.mark.parametrize("field_class", [Metric, Dimension, Fact])
    def test_a_declared_field_is_reachable_by_its_attribute_name(
        self, field_class: type[Field[object]]
    ):
        """The class attribute is the field, carries its kind, and knows its own name."""

        class Sales(SemanticView, view="sales"):
            thing = field_class()

        assert isinstance(Sales.thing, field_class)
        assert Sales.thing.name == "thing"


class TestModelFreezing:
    """A model class cannot be changed once it exists."""

    def test_cannot_add_fields_after_creation(self):
        """Adding a field to a finished model is refused."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        with pytest.raises(AttributeError, match="Cannot modify.*after class creation"):
            Sales.new_field = Metric()

    @pytest.mark.parametrize("attribute", ["_view_name", "_frozen"])
    def test_cannot_rewrite_the_models_own_bookkeeping(self, attribute: str):
        """
        Even the private attributes behind the view name and the freeze refuse assignment.

        Named by their private spelling because that is the only way a caller could reach
        them; the claim is that doing so fails loudly rather than silently re-pointing a model.
        """

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        with pytest.raises(AttributeError, match="Cannot modify.*after class creation"):
            setattr(Sales, attribute, "anything")


class TestMultipleModels:
    """Two models share nothing."""

    def test_multiple_models_have_separate_fields_and_views(self):
        """Each model reports its own fields and queries its own view."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()

        class Products(SemanticView, view="products"):
            price = Metric()
            category = Dimension()

        assert [m.name for m in Sales.metrics()] == ["revenue"]
        assert [m.name for m in Products.metrics()] == ["price"]
        assert [d.name for d in Products.dimensions()] == ["category"]
        assert Sales.dimensions() == []
        assert Sales.query().metrics(Sales.revenue).to_sql().endswith('\nFROM "SALES"')
        assert Products.query().metrics(Products.price).to_sql().endswith('\nFROM "PRODUCTS"')


class TestModelIntrospection:
    """``Model.metrics()`` and ``Model.dimensions()`` list the declared fields."""

    def test_metrics_returns_list_of_metrics(self):
        """``metrics()`` returns every Metric field and nothing else."""

        class Sales(SemanticView, view="sales"):
            revenue = Metric()
            cost = Metric()
            country = Dimension()

        metrics = Sales.metrics()
        assert all(isinstance(m, Metric) for m in metrics)
        assert [m.name for m in metrics] == ["revenue", "cost"]

    def test_metrics_returns_empty_list_if_no_metrics(self):
        """A model with no metrics returns an empty list."""

        class Locations(SemanticView, view="locations"):
            country = Dimension()
            region = Dimension()

        assert Locations.metrics() == []

    def test_dimensions_returns_dimensions_and_facts(self):
        """``dimensions()`` returns Dimension and Fact fields, not metrics."""

        class Orders(SemanticView, view="orders"):
            revenue = Metric()
            region = Dimension()
            date = Fact()

        dims = Orders.dimensions()
        assert all(isinstance(d, Dimension | Fact) for d in dims)
        assert [d.name for d in dims] == ["region", "date"]

    def test_dimensions_returns_empty_list_if_no_dimensions(self):
        """A model with no dimensions or facts returns an empty list."""

        class Metrics(SemanticView, view="metrics"):
            revenue = Metric()
            cost = Metric()

        assert Metrics.dimensions() == []


class TestReservedFieldNames:
    """A field may not shadow a model method."""

    @pytest.mark.parametrize("name", ["query", "metrics", "dimensions", "where", "execute"])
    def test_a_reserved_name_is_refused(self, name: str):
        """Declaring a field under a reserved name raises at class creation."""
        with pytest.raises(ValueError, match=f"'{name}' is reserved"):
            type("Invalid", (SemanticView,), {name: Metric()}, view="invalid")

    def test_error_message_lists_alternatives(self):
        """The error names both ways out: rename the attribute, or keep the column via source=."""
        with pytest.raises(ValueError) as exc_info:
            type("Invalid", (SemanticView,), {"query": Metric()}, view="invalid")

        error_msg = str(exc_info.value)
        assert "'query' is reserved" in error_msg
        assert "'query_field'" in error_msg
        assert "Metric(source='query')" in error_msg


class TestSemanticViewRepr:
    """A model's repr says which view it reads and which fields it declares."""

    def test_subclass_repr_shows_view_name(self) -> None:
        """The repr names the class and its view."""

        class Sales(SemanticView, view="sales_view"):
            revenue = Metric()
            country = Dimension()

        repr_str = repr(Sales)
        assert "SemanticView" in repr_str
        assert "'Sales'" in repr_str
        assert "sales_view" in repr_str

    def test_subclass_repr_shows_metrics(self) -> None:
        """The repr lists metric field names."""

        class Sales(SemanticView, view="sales_view"):
            revenue = Metric()
            cost = Metric()
            country = Dimension()

        repr_str = repr(Sales)
        assert "metrics=" in repr_str
        assert "'revenue'" in repr_str
        assert "'cost'" in repr_str

    def test_subclass_repr_shows_dimensions(self) -> None:
        """The repr lists dimension field names."""

        class Sales(SemanticView, view="sales_view"):
            revenue = Metric()
            country = Dimension()

        repr_str = repr(Sales)
        assert "dimensions=" in repr_str
        assert "'country'" in repr_str

    def test_subclass_repr_shows_facts(self) -> None:
        """The repr lists fact field names."""

        class Sales(SemanticView, view="sales_view"):
            unit_price = Fact()

        repr_str = repr(Sales)
        assert "facts=" in repr_str
        assert "'unit_price'" in repr_str

    def test_subclass_repr_omits_empty_categories(self) -> None:
        """Categories with no fields are left out."""

        class MetricsOnly(SemanticView, view="mo"):
            revenue = Metric()

        repr_str = repr(MetricsOnly)
        assert "dimensions=" not in repr_str
        assert "facts=" not in repr_str

    def test_base_class_repr_does_not_crash(self) -> None:
        """The base class, which has no view, still has a repr."""
        assert repr(SemanticView).startswith("<")
