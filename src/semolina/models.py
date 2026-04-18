"""
Semantic view model base class for Semolina.

This module provides the SemanticView base class that enables ORM-style
model definitions with typed fields and immutable metadata.
"""

import types
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, ClassVar

from .fields import RESERVED_FIELD_NAMES, Dimension, Fact, Field, Metric

if TYPE_CHECKING:
    from .query import _Query


class SemanticViewMeta(type):
    """Metaclass for SemanticView that enforces immutability after creation."""

    def __repr__(cls) -> str:
        """
        Return informative repr for SemanticView subclasses.

        Shows view name and fields grouped by type (metrics, dimensions, facts).
        Falls back to default repr for the base SemanticView class itself.
        """
        view_name = getattr(cls, "_view_name", None)
        if view_name is None:
            return super().__repr__()
        raw_fields = getattr(cls, "_fields", {})
        fields_dict: dict[str, Field[Any]] = dict(raw_fields)
        metrics = [n for n, f in fields_dict.items() if isinstance(f, Metric)]
        dims = [n for n, f in fields_dict.items() if isinstance(f, Dimension)]
        facts = [n for n, f in fields_dict.items() if isinstance(f, Fact)]
        parts = [f"view='{view_name}'"]
        if metrics:
            parts.append(f"metrics={metrics}")
        if dims:
            parts.append(f"dimensions={dims}")
        if facts:
            parts.append(f"facts={facts}")
        return f"<SemanticView '{cls.__name__}' {' '.join(parts)}>"

    def __setattr__(cls, name: str, value: Any) -> None:
        """
        Prevent modification of model classes after creation.

        Args:
            name: Attribute name
            value: Attribute value

        Raises:
            AttributeError: If attempting to modify a frozen model
        """
        # Check if class is frozen
        if getattr(cls, "_frozen", False):
            raise AttributeError(
                f"Cannot modify {cls.__name__}.{name} after class creation. Models are immutable."
            )
        super().__setattr__(name, value)


class SemanticView(metaclass=SemanticViewMeta):
    """
    Base class for semantic view models.

    Models are defined by subclassing SemanticView with a view parameter:

        >>> class Orders(SemanticView, view='orders'):
        ...     total = Metric()
        ...     region = Dimension()
        >>> Orders._view_name
        'orders'

    The __init_subclass__ hook collects field descriptors and freezes
    the model metadata to prevent modification after class creation.

    Introspection:
        Models expose field information via class methods:

            Users.metrics()      # List[Metric] - for aggregation
            Users.dimensions()   # List[Dimension | Fact] - for grouping
    """

    _view_name: ClassVar[str]
    _fields: ClassVar[types.MappingProxyType[str, Field[Any]]]
    _frozen: ClassVar[bool] = False

    def __init_subclass__(cls, view: str | None = None, **kwargs: Any) -> None:
        """
        Called when a class inherits from SemanticView.

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
        fields_dict: dict[str, Field[Any]] = {}
        for name, value in cls.__dict__.items():
            if isinstance(value, Field):
                fields_dict[name] = value

        # Check reserved names that would conflict with query builder methods
        for name in fields_dict:
            if name in RESERVED_FIELD_NAMES:
                raise ValueError(
                    f"Field name '{name}' is reserved and cannot be used. "
                    f"Did you mean: '{name}_field'? Or use source mapping: "
                    f"metric_field = Metric(source='{name}') for column aliasing."
                )

        # Store immutable metadata
        cls._view_name = view
        cls._fields = types.MappingProxyType(fields_dict)
        cls._frozen = True

    @classmethod
    def query(
        cls,
        *,
        metrics: Sequence[Metric[Any]] | None = None,
        dimensions: Sequence[Dimension[Any] | Fact[Any]] | None = None,
        using: str | None = None,
    ) -> "_Query":
        """
        Create a query for this semantic view.

        Entry point for model-centric query construction. Accepts optional
        shorthand keyword arguments for metrics and dimensions, or returns
        a bare _Query for fluent method chaining.

        Shorthand:
            Sales.query(
                metrics=[Sales.revenue],
                dimensions=[Sales.region],
            ).execute()

        Fluent:
            Sales.query().metrics(Sales.revenue).dimensions(
                Sales.region
            ).execute()

        Both styles can be combined -- builder methods are additive:
            Sales.query(metrics=[Sales.revenue]).metrics(Sales.cost)
            # selects both revenue and cost

        Args:
            metrics: Optional list of Metric fields to select
            dimensions: Optional list of Dimension or Fact fields to group by
            using: Optional pool/engine name (defaults to 'default')

        Returns:
            _Query instance bound to this model's view

        Example:
            .. code-block:: python

                cursor = Sales.query(
                    metrics=[Sales.revenue],
                    dimensions=[Sales.region],
                ).execute()
        """
        from .query import _Query as QueryImpl

        q = QueryImpl(_using=using)
        object.__setattr__(q, "_model", cls)

        if metrics:
            q = q.metrics(*metrics)
        if dimensions:
            q = q.dimensions(*dimensions)

        return q

    @classmethod
    def metrics(cls) -> list[Metric[Any]]:
        """
        Get all metric fields for this model.

        Returns a list of Metric descriptors with full metadata. Useful for
        REPL exploration and documentation generation.

        Returns:
            List of Metric field objects (may be empty if no metrics defined)

        Example:
            .. code-block:: pycon

                >>> class Users(SemanticView, view="users"):
                ...     revenue = Metric()
                ...     users_count = Metric()
                ...     country = Dimension()
                ...
                >>> metrics = Users.metrics()
                >>> len(metrics)
                2
                >>> metrics[0].name
                'revenue'
        """
        return [f for f in cls._fields.values() if isinstance(f, Metric)]

    @classmethod
    def dimensions(cls) -> list[Dimension[Any] | Fact[Any]]:
        """
        Get all dimension and fact fields for this model.

        Returns a list of Dimension and Fact descriptors with full metadata.
        Useful for REPL exploration and documentation generation.

        Returns:
            List of Dimension and Fact field objects (may be empty)

        Example:
            .. code-block:: pycon

                >>> class Orders(SemanticView, view="orders"):
                ...     revenue = Metric()
                ...     region = Dimension()
                ...     date = Fact()
                ...
                >>> dims = Orders.dimensions()
                >>> len(dims)
                2
        """
        return [f for f in cls._fields.values() if isinstance(f, Dimension | Fact)]
