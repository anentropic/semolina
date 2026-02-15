"""Tests for field descriptors."""

import pytest

from cubano import Dimension, Fact, Metric
from cubano.fields import Field


class TestFieldValidation:
    """Test field name validation."""

    def test_field_validation_valid_identifier(self):
        """Valid identifiers should be accepted."""

        class TestModel:
            pass

        field = Field()
        # Should not raise
        field.__set_name__(TestModel, 'valid_name')
        assert field.name == 'valid_name'
        assert field.owner == TestModel

    def test_field_validation_rejects_keywords(self):
        """Python keywords should be rejected."""

        class TestModel:
            pass

        field = Field()
        with pytest.raises(ValueError, match="Python keyword"):
            field.__set_name__(TestModel, 'class')

        with pytest.raises(ValueError, match="Python keyword"):
            field.__set_name__(TestModel, 'def')

        with pytest.raises(ValueError, match="Python keyword"):
            field.__set_name__(TestModel, 'return')

    def test_field_validation_rejects_soft_keywords(self):
        """Python soft keywords should be rejected."""

        class TestModel:
            pass

        field = Field()
        with pytest.raises(ValueError, match="soft keyword"):
            field.__set_name__(TestModel, 'match')

        with pytest.raises(ValueError, match="soft keyword"):
            field.__set_name__(TestModel, 'case')

    def test_field_validation_rejects_reserved_names(self):
        """Reserved dict method names should be rejected."""

        class TestModel:
            pass

        field = Field()
        reserved_names = ['keys', 'values', 'items', 'get', 'pop', 'update', 'clear']

        for name in reserved_names:
            with pytest.raises(ValueError, match="reserved"):
                field.__set_name__(TestModel, name)

    def test_field_validation_rejects_invalid_identifiers(self):
        """Invalid Python identifiers should be rejected."""

        class TestModel:
            pass

        field = Field()
        with pytest.raises(ValueError, match="not a valid Python identifier"):
            field.__set_name__(TestModel, '123invalid')

        with pytest.raises(ValueError, match="not a valid Python identifier"):
            field.__set_name__(TestModel, 'invalid-name')


class TestFieldDescriptorProtocol:
    """Test field descriptor protocol behavior."""

    def test_class_level_access_returns_field(self):
        """Class-level field access should return Field instance."""

        class TestModel:
            test_field = Field()

        field = TestModel.test_field
        assert isinstance(field, Field)
        assert field.name == 'test_field'

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
        assert TestModel.revenue.name == 'revenue'

    def test_dimension_inherits_field_behavior(self):
        """Dimension should inherit Field descriptor behavior."""

        class TestModel:
            country = Dimension()

        assert isinstance(TestModel.country, Dimension)
        assert isinstance(TestModel.country, Field)
        assert TestModel.country.name == 'country'

    def test_fact_inherits_field_behavior(self):
        """Fact should inherit Field descriptor behavior."""

        class TestModel:
            unit_price = Fact()

        assert isinstance(TestModel.unit_price, Fact)
        assert isinstance(TestModel.unit_price, Field)
        assert TestModel.unit_price.name == 'unit_price'
