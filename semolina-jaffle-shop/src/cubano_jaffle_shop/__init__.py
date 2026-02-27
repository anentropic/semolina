"""
Cubano semantic view models translated from dbt-jaffle-shop.

Provides Python models for the dbt-jaffle-shop semantic models, enabling
programmatic queries against dbt semantic views from Python.
"""

from .jaffle_models import Customers, Orders, Products

__all__ = ["Orders", "Customers", "Products"]
