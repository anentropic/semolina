"""Tests for field descriptors."""

import pytest

from cubano import Dimension, Fact, Metric
from cubano.fields import Field, NullsOrdering, OrderTerm


class TestFieldValidation:
    """Test field name validation."""

    def test_field_validation_valid_identifier(self):
        """Valid identifiers should be accepted."""

        class TestModel:
            pass

        field = Field()
        # Should not raise
        field.__set_name__(TestModel, "valid_name")
        assert field.name == "valid_name"
        assert field.owner == TestModel

    def test_field_validation_rejects_keywords(self):
        """Python keywords should be rejected."""

        class TestModel:
            pass

        field = Field()
        with pytest.raises(ValueError, match="Python keyword"):
            field.__set_name__(TestModel, "class")

        with pytest.raises(ValueError, match="Python keyword"):
            field.__set_name__(TestModel, "def")

        with pytest.raises(ValueError, match="Python keyword"):
            field.__set_name__(TestModel, "return")

    def test_field_validation_rejects_soft_keywords(self):
        """Python soft keywords should be rejected."""

        class TestModel:
            pass

        field = Field()
        with pytest.raises(ValueError, match="soft keyword"):
            field.__set_name__(TestModel, "match")

        with pytest.raises(ValueError, match="soft keyword"):
            field.__set_name__(TestModel, "case")

    def test_field_validation_rejects_reserved_names(self):
        """Reserved dict method names should be rejected."""

        class TestModel:
            pass

        field = Field()
        reserved_names = ["keys", "values", "items", "get", "pop", "update", "clear"]

        for name in reserved_names:
            with pytest.raises(ValueError, match="reserved"):
                field.__set_name__(TestModel, name)

    def test_field_validation_rejects_invalid_identifiers(self):
        """Invalid Python identifiers should be rejected."""

        class TestModel:
            pass

        field = Field()
        with pytest.raises(ValueError, match="not a valid Python identifier"):
            field.__set_name__(TestModel, "123invalid")

        with pytest.raises(ValueError, match="not a valid Python identifier"):
            field.__set_name__(TestModel, "invalid-name")


class TestFieldDescriptorProtocol:
    """Test field descriptor protocol behavior."""

    def test_class_level_access_returns_field(self):
        """Class-level field access should return Field instance."""

        class TestModel:
            test_field = Field()

        field = TestModel.test_field
        assert isinstance(field, Field)
        assert field.name == "test_field"

    def test_instance_level_access_raises_error(self):
        """Instance-level field access should raise AttributeError."""

        class TestModel:
            test_field = Field()

        instance = TestModel()
        with pytest.raises(AttributeError, match="cannot be accessed from instances"):
            _ = instance.test_field

    def test_field_assignment_raises_error(self):
        """Field assignment should raise AttributeError."""

        class TestModel:
            test_field = Field()

        instance = TestModel()
        with pytest.raises(AttributeError, match="cannot be modified"):
            instance.test_field = "new_value"

    def test_field_deletion_raises_error(self):
        """Field deletion should raise AttributeError."""

        class TestModel:
            test_field = Field()

        instance = TestModel()
        with pytest.raises(AttributeError, match="cannot be deleted"):
            del instance.test_field


class TestFieldSubclasses:
    """Test Metric, Dimension, and Fact field types."""

    def test_metric_inherits_field_behavior(self):
        """Metric should inherit Field descriptor behavior."""

        class TestModel:
            revenue = Metric()

        assert isinstance(TestModel.revenue, Metric)
        assert isinstance(TestModel.revenue, Field)
        assert TestModel.revenue.name == "revenue"

    def test_dimension_inherits_field_behavior(self):
        """Dimension should inherit Field descriptor behavior."""

        class TestModel:
            country = Dimension()

        assert isinstance(TestModel.country, Dimension)
        assert isinstance(TestModel.country, Field)
        assert TestModel.country.name == "country"

    def test_fact_inherits_field_behavior(self):
        """Fact should inherit Field descriptor behavior."""

        class TestModel:
            unit_price = Fact()

        assert isinstance(TestModel.unit_price, Fact)
        assert isinstance(TestModel.unit_price, Field)
        assert TestModel.unit_price.name == "unit_price"


class TestFieldOrdering:
    """Test .asc() and .desc() methods on Field descriptors."""

    def test_desc_returns_order_term(self):
        """Sales.revenue.desc() should return OrderTerm with descending=True."""

        class TestModel:
            revenue = Metric()

        term = TestModel.revenue.desc()
        assert isinstance(term, OrderTerm)
        assert term.field is TestModel.revenue
        assert term.descending is True
        assert term.nulls == NullsOrdering.DEFAULT

    def test_asc_returns_order_term(self):
        """Sales.revenue.asc() should return OrderTerm with descending=False."""

        class TestModel:
            revenue = Metric()

        term = TestModel.revenue.asc()
        assert isinstance(term, OrderTerm)
        assert term.field is TestModel.revenue
        assert term.descending is False
        assert term.nulls == NullsOrdering.DEFAULT

    def test_desc_with_nulls_first(self):
        """Sales.revenue.desc(NullsOrdering.FIRST) should set nulls=FIRST."""

        class TestModel:
            revenue = Metric()

        term = TestModel.revenue.desc(NullsOrdering.FIRST)
        assert isinstance(term, OrderTerm)
        assert term.descending is True
        assert term.nulls == NullsOrdering.FIRST

    def test_asc_with_nulls_last(self):
        """Sales.revenue.asc(NullsOrdering.LAST) should set nulls=LAST."""

        class TestModel:
            revenue = Metric()

        term = TestModel.revenue.asc(NullsOrdering.LAST)
        assert isinstance(term, OrderTerm)
        assert term.descending is False
        assert term.nulls == NullsOrdering.LAST

    def test_desc_on_dimension(self):
        """Sales.country.desc() should work on Dimension fields."""

        class TestModel:
            country = Dimension()

        term = TestModel.country.desc()
        assert isinstance(term, OrderTerm)
        assert term.field is TestModel.country

    def test_desc_on_fact(self):
        """Sales.unit_price.desc() should work on Fact fields."""

        class TestModel:
            unit_price = Fact()

        term = TestModel.unit_price.desc()
        assert isinstance(term, OrderTerm)
        assert term.field is TestModel.unit_price

    def test_order_term_is_frozen(self):
        """OrderTerm attributes should not be modifiable after creation."""

        class TestModel:
            revenue = Metric()

        term = TestModel.revenue.desc()
        # Frozen dataclass should prevent modification
        with pytest.raises((AttributeError, TypeError)):
            term.descending = False  # type: ignore[misc]

    def test_order_term_repr(self):
        """repr(Sales.revenue.desc(NullsOrdering.FIRST)) should produce readable output."""

        class TestModel:
            revenue = Metric()

        term_desc_nulls_first = TestModel.revenue.desc(NullsOrdering.FIRST)
        repr_str = repr(term_desc_nulls_first)
        assert "OrderTerm" in repr_str
        assert "revenue" in repr_str
        assert "DESC" in repr_str
        assert "NULLS FIRST" in repr_str
