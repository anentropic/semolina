"""Tests for IntrospectedField and IntrospectedView frozen dataclasses."""

from __future__ import annotations

import pytest

from semolina.codegen.introspector import IntrospectedField, IntrospectedView


class TestIntrospectedField:
    """Tests for IntrospectedField frozen dataclass."""

    def test_create_metric_field(self) -> None:
        """IntrospectedField can be created with metric field type."""
        field = IntrospectedField(
            name="revenue",
            field_type="metric",
            data_type="int",
        )
        assert field.name == "revenue"
        assert field.field_type == "metric"
        assert field.data_type == "int"
        assert field.description == ""

    def test_create_dimension_field(self) -> None:
        """IntrospectedField can be created with dimension field type."""
        field = IntrospectedField(
            name="country",
            field_type="dimension",
            data_type="str",
        )
        assert field.name == "country"
        assert field.field_type == "dimension"
        assert field.data_type == "str"

    def test_create_fact_field(self) -> None:
        """IntrospectedField can be created with fact field type."""
        field = IntrospectedField(
            name="cost",
            field_type="fact",
            data_type="float",
        )
        assert field.field_type == "fact"

    def test_description_default_empty_string(self) -> None:
        """IntrospectedField description defaults to empty string."""
        field = IntrospectedField(name="revenue", field_type="metric", data_type="int")
        assert field.description == ""

    def test_description_can_be_set(self) -> None:
        """IntrospectedField description can be provided."""
        field = IntrospectedField(
            name="revenue",
            field_type="metric",
            data_type="int",
            description="Total revenue",
        )
        assert field.description == "Total revenue"

    def test_is_frozen(self) -> None:
        """IntrospectedField is immutable (frozen dataclass)."""
        field = IntrospectedField(name="revenue", field_type="metric", data_type="int")
        with pytest.raises((AttributeError, TypeError)):
            field.name = "other"  # type: ignore[misc]

    def test_data_type_none_for_unmappable(self) -> None:
        """IntrospectedField data_type can be None for unmappable types."""
        field = IntrospectedField(
            name="geo",
            field_type="dimension",
            data_type=None,
        )
        assert field.data_type is None

    def test_equality(self) -> None:
        """Two IntrospectedFields with identical values are equal."""
        f1 = IntrospectedField(name="revenue", field_type="metric", data_type="int")
        f2 = IntrospectedField(name="revenue", field_type="metric", data_type="int")
        assert f1 == f2

    def test_inequality(self) -> None:
        """Two IntrospectedFields with different values are not equal."""
        f1 = IntrospectedField(name="revenue", field_type="metric", data_type="int")
        f2 = IntrospectedField(name="cost", field_type="metric", data_type="int")
        assert f1 != f2

    def test_source_name_defaults_to_none(self) -> None:
        """IntrospectedField source_name defaults to None."""
        field = IntrospectedField(name="revenue", field_type="metric", data_type="int")
        assert field.source_name is None

    def test_source_name_can_be_set(self) -> None:
        """IntrospectedField source_name can be set for quoted-lowercase columns."""
        field = IntrospectedField(
            name="order_id",
            field_type="dimension",
            data_type="str",
            source_name="order_id",
        )
        assert field.source_name == "order_id"

    def test_source_name_preserved_in_frozen_dataclass(self) -> None:
        """IntrospectedField source_name is part of the frozen dataclass identity."""
        f1 = IntrospectedField(name="order_id", field_type="dimension", data_type="str")
        f2 = IntrospectedField(
            name="order_id", field_type="dimension", data_type="str", source_name="order_id"
        )
        assert f1 != f2


class TestIntrospectedView:
    """Tests for IntrospectedView frozen dataclass."""

    def test_create_basic_view(self) -> None:
        """IntrospectedView can be created with required fields."""
        view = IntrospectedView(
            view_name="sales_view",
            class_name="Sales",
            fields=[],
        )
        assert view.view_name == "sales_view"
        assert view.class_name == "Sales"
        assert view.fields == []

    def test_create_view_with_fields(self) -> None:
        """IntrospectedView can hold a list of IntrospectedFields."""
        fields = [
            IntrospectedField(name="revenue", field_type="metric", data_type="int"),
            IntrospectedField(name="country", field_type="dimension", data_type="str"),
        ]
        view = IntrospectedView(
            view_name="sales_view",
            class_name="Sales",
            fields=fields,
        )
        assert len(view.fields) == 2
        assert view.fields[0].name == "revenue"
        assert view.fields[1].name == "country"

    def test_is_frozen(self) -> None:
        """IntrospectedView is immutable (frozen dataclass)."""
        view = IntrospectedView(view_name="sales_view", class_name="Sales", fields=[])
        with pytest.raises((AttributeError, TypeError)):
            view.view_name = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two IntrospectedViews with identical values are equal."""
        fields = [IntrospectedField(name="revenue", field_type="metric", data_type="int")]
        v1 = IntrospectedView(view_name="sales_view", class_name="Sales", fields=fields)
        v2 = IntrospectedView(view_name="sales_view", class_name="Sales", fields=fields)
        assert v1 == v2

    def test_inequality(self) -> None:
        """Two IntrospectedViews with different view names are not equal."""
        v1 = IntrospectedView(view_name="sales_view", class_name="Sales", fields=[])
        v2 = IntrospectedView(view_name="other_view", class_name="Sales", fields=[])
        assert v1 != v2

    def test_fields_mixed_types(self) -> None:
        """IntrospectedView fields can mix metric, dimension, and fact types."""
        view = IntrospectedView(
            view_name="sales_view",
            class_name="Sales",
            fields=[
                IntrospectedField(name="revenue", field_type="metric", data_type="int"),
                IntrospectedField(name="country", field_type="dimension", data_type="str"),
                IntrospectedField(name="cost", field_type="fact", data_type="float"),
            ],
        )
        assert len(view.fields) == 3
