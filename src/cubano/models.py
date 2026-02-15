"""Semantic view model base class for Cubano.

This module provides the SemanticView base class that enables ORM-style
model definitions with typed fields and immutable metadata.
"""

import types
from typing import Any

from .fields import Field


class SemanticViewMeta(type):
    """Metaclass for SemanticView that enforces immutability after creation."""

    def __setattr__(cls, name: str, value: Any) -> None:
        """Prevent modification of model classes after creation.

        Args:
            name: Attribute name
            value: Attribute value

        Raises:
            AttributeError: If attempting to modify a frozen model
        """
        # Check if class is frozen
        if getattr(cls, '_frozen', False):
            raise AttributeError(
                f"Cannot modify {cls.__name__}.{name} after class creation. "
                f"Models are immutable."
            )
        super().__setattr__(name, value)


class SemanticView(metaclass=SemanticViewMeta):
    """Base class for semantic view models.

    Models are defined by subclassing SemanticView with a view parameter:

        class Sales(SemanticView, view='sales'):
            revenue = Metric()
            country = Dimension()

    The __init_subclass__ hook collects field descriptors and freezes
    the model metadata to prevent modification after class creation.
    """

    _view_name: str
    _fields: types.MappingProxyType
    _frozen: bool = False

    def __init_subclass__(cls, view: str | None = None, **kwargs: Any) -> None:
        """Called when a class inherits from SemanticView.

        Collects Field descriptors and stores immutable metadata.

        Args:
            view: The semantic view name (required)
            **kwargs: Additional keyword arguments for cooperative inheritance

        Raises:
            TypeError: If view parameter is not provided
        """
        super().__init_subclass__(**kwargs)

        # Validate view parameter
        if view is None:
            raise TypeError(
                f"{cls.__name__} must specify a view parameter. "
                f"Example: class {cls.__name__}(SemanticView, view='view_name')"
            )

        # Collect fields from class definition
        fields_dict = {}
        for name, value in cls.__dict__.items():
            if isinstance(value, Field):
                fields_dict[name] = value

        # Store immutable metadata
        cls._view_name = view
        cls._fields = types.MappingProxyType(fields_dict)
        cls._frozen = True
