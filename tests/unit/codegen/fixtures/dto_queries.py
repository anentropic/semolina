"""
Module-level queries the DTO codegen CLI is pointed at by dotted path.

Stands in for a user's ``myapp/queries.py``. The CLI's positional argument is a dotted path
to a module-level query object (D-01), and ``semolina.codegen.query_resolver.resolve_query``
imports that path for real — so the queries below have to be *module-level attributes of an
importable module*, which is exactly what this file is. Building them inside a test would
test the renderer and skip the resolution.

Both queries are built on :class:`type_fidelity_probe.TypeFidelityView`, the model of the
live DuckDB probe view, so the CLI's probe resolves a real result schema carrying a real
``decimal128`` metric rather than a synthetic one.
"""

from __future__ import annotations

from type_fidelity_probe import TypeFidelityView as View

value_by_region = (
    View.query()
    .metrics(View.total_order_value, View.n_order_totals)
    .dimensions(View.region)
    .where(View.region == "US")
    .order_by(View.region)
    .limit(5)
)
"""
The headline query: a decimal metric, a COUNT metric and a dimension.

Carries a filter, an ordering and a limit deliberately. The DTO derives from the projection
alone (D-02), so a query with all three is a legal input and must generate the same class as
its unfiltered twin — and the CLI has to strip them before probing or Snowflake's
bound-parameter ``ExecuteSchema`` refusal would be reachable from the published command.

The attribute name is chosen so its PascalCase form (``ValueByRegion``) is worth asserting.
"""

counts_by_region = (
    View.query().metrics(View.total_order_count, View.min_order_count).dimensions(View.region)
)
"""
A second query, for the several-paths-in-one-invocation case.

Its attribute name yields ``CountsByRegion``, which shares no class name with
:data:`value_by_region` — a collision is refused by the CLI rather than silently emitting two
classes of the same name into one file, and this pair is the case that must *not* be refused.
"""

not_a_query = "this is a string, not a query"
"""
A module-level attribute that is not a query.

The CLI must refuse a dotted path resolving to this and name the type it actually found,
which is the difference between an error a user can act on and one that only says something
went wrong.
"""
