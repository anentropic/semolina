.. _howto-dto-codegen:

How to generate a typed DTO from a query
=========================================

``semolina codegen-dto`` takes a query you already wrote, asks your warehouse what that
query would return, and prints a Pydantic class typed and aliased for those columns.
Redirect stdout, commit the file, hand the class to
:py:meth:`~semolina.cursor.SemolinaCursor.into`.

It is the sibling of ``semolina codegen``, which generates the
:py:class:`~semolina.models.SemanticView` class describing a whole view. A view is the
superset of every metric and dimension it carries; a query returns a subset, with the types
its aggregations produced. One class per view cannot describe both, which is why a result
DTO is generated from a query rather than from a view.

Generate a DTO from a module-level query
-----------------------------------------

Codegen resolves an importable object, so the query has to live at module scope:

.. code-block:: python

   # myapp/queries.py
   from myapp.models import Sales

   revenue_by_country = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
   )

Point the command at it by dotted path:

.. code-block:: bash

   semolina codegen-dto myapp.queries.revenue_by_country --backend snowflake

The class arrives on stdout:

.. code-block:: python

   """
   Generated result DTOs. Do not edit.

   Backend: snowflake

   Column aliases below are the spellings this backend returns for this query, and the
   annotations reflect its own aggregation result typing. Another warehouse needs a
   regenerated class -- these are not portable and are not meant to be.

   Classes:
       RevenueByCountry -- myapp.queries.revenue_by_country (dialect: SnowflakeDialect, probe route: execute-schema)
   """

   from __future__ import annotations

   import decimal

   import pydantic


   class RevenueByCountry(pydantic.BaseModel):
       """Result DTO for myapp.queries.revenue_by_country (probe route: execute-schema)."""

       revenue: decimal.Decimal | None = pydantic.Field(
           validation_alias='AGG("REVENUE")'
       )
       country: str = pydantic.Field(
           validation_alias="COUNTRY"
       )

Field names come from your model, so ``Sales.revenue`` gives the DTO a field named
``revenue``. The ``validation_alias`` is the column name Snowflake really returns for that
field, and the annotation is the type Snowflake said the column would arrive as. Neither is
read from the model's declared field types.

The class name comes from the attribute name: ``revenue_by_country`` becomes
``RevenueByCountry``.

No row of your data is fetched. Codegen asks the warehouse to type the query rather than to
run it, the same probe behind :ref:`semolina codegen --check <howto-codegen-check>`.

The generated class is what :py:meth:`~semolina.cursor.SemolinaCursor.into` wants:

.. code-block:: python

   from myapp.dtos import RevenueByCountry
   from myapp.queries import revenue_by_country

   with revenue_by_country.execute() as cursor:
       rows = cursor.into(RevenueByCountry)

Credentials come from the same places ``semolina codegen`` reads them: the
``[connections.<backend>]`` section of ``.semolina.toml``, then prefixed environment
variables, then a ``.env`` file. ``--backend duckdb`` wants a ``--database`` path, or
``DUCKDB_DATABASE`` in the environment. See :ref:`howto-codegen-credentials`.

Point codegen at the query you already wrote
---------------------------------------------

A query's ``where()``, ``order_by()`` and ``limit()`` clauses are stripped before the probe.
The DTO describes the projection and nothing else, so these two generate the same class:

.. code-block:: python

   revenue_by_country = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
   )

   top_us_revenue = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .where(Sales.country == "US")
       .order_by(Sales.revenue.desc())
       .limit(10)
   )

A filter decides which rows come back, not what type each column is. You do not need to keep
an unfiltered twin of a query around for codegen to look at: point it at the query your
application actually runs.

Write the output to a file
--------------------------

.. code-block:: bash

   semolina codegen-dto myapp.queries.revenue_by_country \
       --backend snowflake > myapp/dtos.py

There is no ``--output`` flag; redirect stdout as you would with any CLI tool. Every
diagnostic goes to stderr, so the file captures only Python.

Format the generated output
---------------------------

By default the command prints valid but unformatted Python. Install the optional
``codegen-lint`` extra and the generated source goes through ruff first, formatted with its
imports sorted:

.. code-block:: bash

   pip install semolina[codegen-lint]
   # or
   uv add "semolina[codegen-lint]"

Without the extra you still get the DTO on stdout, plus a short reminder on stderr. The
reminder stays out of stdout, so ``> myapp/dtos.py`` captures only the Python.

Generate several DTOs into one file
------------------------------------

Pass several dotted paths in one call:

.. code-block:: bash

   semolina codegen-dto \
       myapp.queries.revenue_by_country \
       myapp.queries.orders_by_month \
       --backend snowflake > myapp/dtos.py

The classes appear in one output block over a single shared import section, and each one
names its own dotted path and probe route in its docstring.

Two paths whose attribute names produce the same class name are refused rather than
generated. A duplicate class in one module is not an error Python reports: the second
definition replaces the first, so you would get a file that imports cleanly and is missing a
DTO. Generate those two separately, using ``--name`` to rename one.

Rename the generated class
--------------------------

.. code-block:: bash

   semolina codegen-dto myapp.queries.revenue_by_country \
       --backend snowflake --name CountryRevenueRow

``--name`` renames a single class, so it takes a single query path. Passing it alongside
several exits ``2`` before anything is imported.

The value becomes the class's own name in the generated file, so it has to be a valid Python
identifier and not a keyword; anything else exits ``2`` as well, before the query is
resolved.

Regenerate when you change warehouse
-------------------------------------

A generated DTO belongs to the backend it was probed against, and its header says which one.

The aliases are the visible half of that. The same query names its result columns
differently on each warehouse:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: python

         revenue: decimal.Decimal | None = pydantic.Field(
             validation_alias='AGG("REVENUE")'
         )
         country: str = pydantic.Field(validation_alias="COUNTRY")

      Snowflake folds unquoted identifiers to upper case, and it applies that folding to
      the metric name *inside* the quotes as well. A metric stored as ``gross revenue``
      arrives as ``AGG("GROSS REVENUE")``, not as the ``AGG("gross revenue")`` the query
      had to send to reach it.

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: python

         revenue: int | None = pydantic.Field(
             validation_alias="measure(revenue)"
         )
         country: str = pydantic.Field(validation_alias="country")

      Databricks leaves dimension names alone and wraps a metric in ``measure()``, lower
      case, dropping any backticks the query needed — a metric named ``gross revenue``
      arrives as ``measure(gross revenue)``. Note the annotation: a ``SUM`` over an
      integer column, which Snowflake reports as a ``DECIMAL``, comes back here as a
      ``BIGINT``.

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: python

         revenue: decimal.Decimal | None = pydantic.Field(
             validation_alias="revenue"
         )
         country: str = pydantic.Field(validation_alias="country")

      DuckDB's ``semantic_view()`` returns bare field names, so the alias repeats the field
      name.

The annotation is the other half, and it is not guaranteed to agree across the three either.
Aggregation result typing is the warehouse's own decision: a ``SUM`` over an integer column
comes back as a ``BIGINT`` from one warehouse and a ``DECIMAL`` from another. Codegen prints
the type it measured and does not try to paper over the difference, because there is no
annotation that would be right on all three at once.

So a generated DTO does not travel. Regenerate it against the warehouse you deploy to, and
read the header when you want to know which warehouse a committed file came from. See
:ref:`howto-result-column-names` for the column-naming rules behind those three tabs.

Replace the Any annotations
---------------------------

When a result column's Arrow type has no clean Python equivalent, codegen annotates the
field ``Any`` and writes the Arrow type into a comment above it rather than guessing:

.. code-block:: python

   # TODO: struct<iso: string>
   origin: Any = pydantic.Field(validation_alias="ORIGIN")

The comment is the signal, not the annotation. ``Any`` satisfies a type checker by
definition, so a DTO carrying one passes basedpyright strict while telling you nothing about
that column. Search the generated file for ``TODO:`` and replace each one with the type you
want the column to arrive as.

Know why every metric is optional
----------------------------------

Every metric field is annotated ``| None``, whatever the query:

.. code-block:: python

   revenue: decimal.Decimal | None = pydantic.Field(
       validation_alias='AGG("REVENUE")'
   )

A group whose inputs are all NULL returns NULL from ``SUM``, ``AVG``, ``MIN`` and ``MAX``.
``COUNT`` returns ``0`` instead, so a ``COUNT`` metric is annotated wider than it strictly
needs to be. That over-approximation is deliberate, because the error is asymmetric. Too
wide costs you an ``is None`` check you did not need. Too narrow is a bug that stays
invisible until the first NULL arrives: a ``ValidationError`` under ``validate=True``, or a
``None`` sitting in a field you declared non-optional on the default path.

Dimensions and facts are columns rather than aggregates, so codegen annotates them with the
type the warehouse reports and nothing more. See :ref:`explanation-type-fidelity` for the
null cases and why ``COUNT`` is treated like ``SUM``.

Read the probe route in the header
-----------------------------------

Codegen prefers to ask the driver to type the query without running it. Not every driver
offers that call. When one refuses, codegen runs the query wrapped to return no rows and
reads the schema off the empty result instead. No data row is fetched on either route, and
the generated file records which one answered:

.. code-block:: text

   RevenueByCountry -- myapp.queries.revenue_by_country (dialect: DatabricksDialect, probe route: zero-row)

``execute-schema`` means the driver typed the query. ``zero-row`` means it declined and the
fallback ran. The two routes produce the same annotations and the same aliases, so the label
tells you how the answer was obtained rather than how much to trust it.

Which route you get is a property of the driver, not of your query. Snowflake and DuckDB
answer the describe-only call, so they report ``execute-schema``. The Databricks ADBC driver
does not implement it and reports ``zero-row`` — measured against a live workspace on
2026-08-15, where the wrapped query typed the schema and the generated class round-tripped
through :py:meth:`~semolina.cursor.SemolinaCursor.into`.

Know what a dotted path imports
--------------------------------

Resolving ``myapp.queries.revenue_by_country`` imports ``myapp.queries``, which runs that
module top to bottom: connections open, environment variables are read, decorators fire.
That is inherent to generating code from an importable object, and it is what
``--backend dotted.path.ClassName`` has always done. Point the command at code you trust.

The working directory is appended to ``sys.path``, never prepended. A package at your
project root therefore resolves without being installed, while a file sitting in the working
directory cannot shadow an installed distribution of the same name.

Exit codes
----------

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - Exit code
     - Meaning
   * - ``0``
     - Success
   * - ``1``
     - Unexpected error
   * - ``2``
     - Invalid option -- an unrecognised or omitted ``--backend``, a ``QUERY_PATH`` that
       does not resolve to a query, or ``--name`` passed with more than one query
   * - ``3``
     - View not found in the warehouse
   * - ``4``
     - Connection or authentication failure
   * - ``6``
     - Probe failed, or a projected field matched no result column -- no DTO was written

.. note::

   There is no ``5``. That code belongs to ``semolina codegen --check``, where it means
   annotation drift, and this command has no ``--check``.

   ``3`` and ``4`` are reported by an engine's own ``connect()``, which you reach through
   ``--backend dotted.path.ClassName``. On the three built-in backends a driver that cannot
   connect fails inside the probe instead, and that exits ``6``. Read stderr rather than
   inferring the cause from the code.

Exit ``6`` covers the two ways a DTO can fail to be worth writing: the warehouse would not
describe the query, or a projected field matched no column in the result it described.
Neither writes anything to stdout, and the message on stderr names the field along with
every column the result actually carried.

See also
--------

- :ref:`howto-typed-results` -- passing the generated class to ``.into()``, and the
  hand-written route it replaces
- :ref:`howto-codegen` -- generating the ``SemanticView`` model class the query is built from
- :ref:`explanation-type-fidelity` -- why the warehouse decides the annotation and what a
  generated one promises
- :ref:`explanation-duckdb-vs-warehouse` -- which of the per-backend differences above a
  DuckDB-only test suite cannot catch
- :ref:`howto-codegen-credentials` -- environment variables, .env files, and config file
  fallback
- :ref:`reference-cli` -- every flag, argument, and exit code
