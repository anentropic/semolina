.. _howto-dto-codegen:

How to generate a typed DTO from a query
=========================================

``semolina codegen-dto`` asks your warehouse what a query would return and writes a Pydantic
class typed and aliased for those columns. Commit the file, hand the class to
:py:meth:`~semolina.cursor.SemolinaCursor.into`, which needs the ``arrowmodel`` extra:

.. code-block:: bash

   pip install "semolina[arrowmodel]"

Codegen itself does not need it. It is the ``.into()`` call on the other side that does, so a
CI job that only regenerates DTOs can skip it. See :ref:`howto-typed-results`.

There are three ways to say which query. Point it at one you already wrote, name a view and
its fields on the command line, or declare the whole set in ``pyproject.toml``.

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

Generate a DTO without writing a query first
---------------------------------------------

The dotted-path route needs a query object at module scope to point at. If you build your
queries inside a request handler rather than hoisting them to module level, there is nothing
to point at -- so name the view and the fields on the command line instead:

.. code-block:: bash

   semolina codegen-dto --backend snowflake \
       --view analytics.sales \
       --metrics revenue \
       --dimensions country

Nothing is imported. Codegen builds the query for you, probes it, and emits the class:

.. code-block:: python

   class Sales(pydantic.BaseModel):
       """Result DTO for view 'analytics.sales' metrics=[revenue] dimensions=[country] (probe route: execute-schema)."""

       revenue: decimal.Decimal | None = pydantic.Field(
           validation_alias='AGG("REVENUE")'
       )
       country: str = pydantic.Field(
           validation_alias="COUNTRY"
       )

That is the same class the dotted-path route generates for the same projection, because it
is the same query: the field names go through your dialect's own builder, so the aliases and
the annotations are whatever that warehouse answered.

The class is named after the view's last segment, so ``analytics.sales`` gives you ``Sales``
and ``analytics.daily_sales`` gives you ``DailySales``. Pass ``--name`` for anything else.

``--metrics`` and ``--dimensions`` take a comma-separated list, and both can be repeated.
These two commands are the same:

.. code-block:: bash

   semolina codegen-dto --view analytics.sales --metrics revenue,order_count -b snowflake
   semolina codegen-dto --view analytics.sales --metrics revenue --metrics order_count -b snowflake

The names you give are the warehouse's field names *and* the generated attribute names, so
each one has to be a plain Python identifier: not a Python keyword, and not one of the names
the query builder reserves (``query``, ``metrics``, ``dimensions``, ``where``, ``filter``,
``order_by``, ``limit``, ``execute``, ``to_sql``, ``using``, and the dict-like ``keys``,
``values``, ``items``, ``get``, ``pop``, ``update``, ``clear``). That is the same rule a
hand-written :py:class:`~semolina.models.SemanticView` field obeys, and a name that breaks it
exits ``2`` before anything connects.

A warehouse field spelled in a way Python cannot reach -- ``gross revenue``, say -- is the
one case this route has no answer for. It needs a model declaring
``gross_revenue = Metric(source="gross revenue")`` and a query built on that.

A field the view does not carry exits ``6``, and the message lists the columns the result
did carry. That is the mistake this route makes easy: the names are typed by hand rather
than checked by an import, and your editor cannot tell you that ``total_valu`` is a typo.

You still need a model to run the query
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--view`` replaces the importable *query*, not the model. A DTO describes a result, and
producing a result still goes through :py:meth:`Model.query() <semolina.models.SemanticView.query>`
on a :py:class:`~semolina.models.SemanticView` subclass, whatever generated the class you
convert into:

.. code-block:: python

   from myapp.dtos import Sales
   from myapp.models import Sales as SalesView

   with SalesView.query(
       metrics=[SalesView.revenue],
       dimensions=[SalesView.country],
   ).execute() as cursor:
       rows = cursor.into(Sales)

Generate that model once with ``semolina codegen`` (see :ref:`howto-codegen`) and keep it.
The projection you pass to ``--metrics`` and ``--dimensions`` has to match the projection the
query selects, or the DTO's aliases will not bind to the columns that come back.

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
       --backend snowflake --output myapp/dtos.py

The directory has to exist; codegen will not create one, because a generated DTO lives in
the package that imports it. Nothing is written until every class has rendered, so a run
that fails partway leaves an already-committed file exactly as it was.

Redirecting stdout works as well, and always has. Every diagnostic goes to stderr, so the
file captures only Python:

.. code-block:: bash

   semolina codegen-dto myapp.queries.revenue_by_country \
       --backend snowflake > myapp/dtos.py

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
generated, and so are two config entries over the same view. A duplicate class in one module
is not an error Python reports: the second definition replaces the first, so you would get a
file that imports cleanly and is missing a DTO. Rename one with ``--name`` or with its
``name`` key.

Declare every DTO in pyproject.toml
------------------------------------

Past two or three DTOs, the command line is something nobody remembers between releases.
Write the set down instead, in the file that already describes your build:

.. code-block:: toml

   [tool.semolina.dto]
   backend = "snowflake"
   output = "myapp/dtos.py"

   [[tool.semolina.dto.entries]]
   query = "myapp.queries.revenue_by_country"

   [[tool.semolina.dto.entries]]
   query = "myapp.queries.orders_by_month"

   [[tool.semolina.dto.entries]]
   name = "TopProducts"
   view = "analytics.products"
   metrics = ["units_sold"]
   dimensions = ["product_name"]

Then regenerate all of them at once:

.. code-block:: bash

   semolina codegen-dto

The classes arrive in ``myapp/dtos.py`` in the order the file declares them, over one shared
import block. Ordering matters more than it looks: codegen never sorts them, so inserting an
entry produces a diff of that entry rather than of the whole module.

Settings on the section itself:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Meaning
   * - ``backend``
     - What ``--backend`` would have said. Required unless you pass the flag.
   * - ``database``
     - The DuckDB database path, for ``backend = "duckdb"``.
   * - ``output``
     - Where to write. Omit it and the module goes to stdout.

And on each ``[[tool.semolina.dto.entries]]`` table, one of two shapes:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Meaning
   * - ``query``
     - Dotted path to a module-level query, as the positional argument takes.
   * - ``view``
     - A view name, with ``metrics`` and ``dimensions`` as arrays of field names.
   * - ``name``
     - The generated class name. Omit it and the name is derived, from the query attribute
       or from the view.

Relative ``output`` and ``database`` paths resolve against the directory holding
``pyproject.toml``, not against your shell's working directory, so the declaration means the
same file wherever you run the command from.

``--backend``, ``--database`` and ``--output`` still work and override what the section says,
so a test suite can regenerate the same declared DTOs against a local DuckDB without
touching the committed config:

.. code-block:: bash

   semolina codegen-dto --backend duckdb --database tests/fixtures.db \
       --output tests/dtos_duckdb.py

.. warning::

   ``DUCKDB_DATABASE`` in the environment beats the section's ``database`` too, not only the
   absence of ``--database``. The flag reads that variable as its own fallback, and it does
   so before the config is consulted, so a stray export probes a different database than the
   committed file names.

Credentials are not part of this. The section names a *backend*, which is a label. The
connection details still come from ``.semolina.toml`` and the environment, which is where
they belong: ``pyproject.toml`` gets committed and those two do not. See
:ref:`howto-codegen-credentials`.

To read a file other than ``./pyproject.toml``, pass ``--config``. It cannot be combined
with a query path or ``--view``: the config declares what a project generates, and
generating something else alongside it would leave the file describing only part of its own
output.

An unrecognized key is an error rather than something quietly ignored -- ``dimension`` for
``dimensions``, ``outputs`` for ``output``. A config is written once and trusted for a long
time, and a typo that generates a subtly wrong DTO is found by whoever notices the missing
column, not by whoever made it.

.. _howto-dto-codegen-check:

Check a committed DTO in CI
----------------------------

``--check`` compares the committed file against what the warehouse would produce now. It
writes nothing, and exits ``5`` if they have diverged:

.. code-block:: bash

   semolina codegen-dto --check

With a ``[tool.semolina.dto]`` section that is the whole invocation: it reads the file
``output`` names, so it verifies exactly what the bare command would write. Without one,
point it at the file with ``--output``:

.. code-block:: bash

   semolina codegen-dto myapp.queries.revenue_by_country \
       --backend snowflake --output myapp/dtos.py --check

The report goes to stderr, one row per field:

.. code-block:: text

   semolina codegen-dto --check: RevenueByCountry
   ┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
   ┃ Field   ┃ Committed              ┃ Generated              ┃ Status ┃
   ┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
   │ revenue │ decimal.Decimal | None │ decimal.Decimal | None │ match  │
   │ country │ str                    │ str                    │ match  │
   └─────────┴────────────────────────┴────────────────────────┴────────┘

Two alias columns appear alongside those when an alias has moved, and stay hidden when none
has. That is the check the model-level ``semolina codegen --check`` cannot do, because a
model field has no alias — and it is the one most likely to fire, since a DTO's aliases are
the result-column spellings of **one** backend. A file generated against Snowflake and
checked against Databricks drifts on every metric, which is the header's pinning claim
enforced rather than merely printed.

Drift is also reported when the query gained or lost a field, when the committed file has no
class of that name, and when it has a class nothing generates any more — the last being what
a config entry deleted without regenerating leaves behind.

.. tip:: Hand-edited ``Any`` annotations do not drift

   Replacing a generated ``Any`` with a real type is what the
   `Replace the Any annotations`_ section tells you to do, so ``--check`` treats a generated
   ``Any`` as agreeing with whatever you wrote. Codegen has no opinion about that column, so
   it has none to contradict. The row still appears, with a note saying the annotation is
   yours.

   It works one way only. A committed ``Any`` against a resolved annotation *is* drift:
   there codegen has learned a type your file does not know, and regenerating gains you a
   real one.

A run that exits ``5`` has worked correctly. Exit ``1`` means the committed file could not
be parsed, and ``2`` means you did not say which file to check.

Rename the generated class
--------------------------

.. code-block:: bash

   semolina codegen-dto myapp.queries.revenue_by_country \
       --backend snowflake --name CountryRevenueRow

``--name`` renames a single class, so it takes a single query -- one dotted path, or one
``--view``. Passing it alongside several exits ``2`` before anything is imported, and so
does passing it with ``--config``, where each entry names itself with its own ``name`` key.

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
      case, dropping any backticks the query needed -- a metric named ``gross revenue``
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
does not implement it and reports ``zero-row`` -- measured against a live workspace on
2026-08-15, where the wrapped query typed the schema and the generated class round-tripped
through :py:meth:`~semolina.cursor.SemolinaCursor.into`.

Know what a dotted path imports
--------------------------------

Resolving ``myapp.queries.revenue_by_country`` imports ``myapp.queries``, which runs that
module top to bottom: connections open, environment variables are read, decorators fire.
That is inherent to generating code from an importable object, and it is what
``--backend dotted.path.ClassName`` has always done. Point the command at code you trust.

The working directory is appended to ``sys.path``, never prepended. A package sitting
directly in your project root therefore resolves without being installed, while a file in
the working directory cannot shadow an installed distribution of the same name.

On a ``src/`` layout the package is not in the working directory, so that fallback does not
reach it and a dotted path resolves only once the project is installed -- ``uv sync``, or
``pip install -e .``. A path that will not import reports the module it could not find and
exits ``2``.

``--view`` imports nothing at all: it names the view and its fields directly, so there is no
module to run. The same split holds inside a config file -- an entry with ``query`` imports,
an entry with ``view`` does not.

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
     - Invalid option -- an unrecognized or omitted ``--backend``, a ``QUERY_PATH`` that
       does not resolve to a query, a ``--view`` field list a model could not declare, a
       malformed ``[tool.semolina.dto]`` section, two routes given at once, or ``--name``
       passed with more than one DTO
   * - ``3``
     - View not found in the warehouse
   * - ``4``
     - Connection or authentication failure
   * - ``5``
     - Annotation drift -- a committed DTO no longer matches the result schema
   * - ``6``
     - Probe failed, or a projected field matched no result column -- no DTO was written

.. note::

   ``5`` means here what it means for ``semolina codegen --check``: a committed generated
   file no longer matches the result schema. Only a ``--check`` run can return it.

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
