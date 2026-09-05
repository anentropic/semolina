.. _tutorial-warehouse-models:

Generate models from your warehouse
===================================

Every model in these tutorials was written by hand, from a view whose shape you
already knew. That does not scale past a few fields, and it goes stale silently
when someone changes the view. In this tutorial you will stop writing them: the
``semolina`` command reads a semantic view, or probes a query, and prints the
Python class.

You will generate two classes. ``semolina codegen`` writes the
:py:class:`~semolina.models.SemanticView` model that describes the whole view.
``semolina codegen-dto`` writes the Pydantic response class for one query's
result, aliased and typed for the warehouse it asked.

**Prerequisites:** :ref:`tutorial-testing-queries`, and its ``reports.py``,
``conftest.py`` and ``test_reports.py``. The commands below run against the same
``tutorial.db``.

.. tip:: Formatted output

   Both commands print valid but unformatted Python by default. Install the
   ``codegen-lint`` extra and the generated source goes through ruff first, with
   its imports sorted:

   .. code-block:: bash

      pip install "semolina[codegen-lint]"

1. Read the view
----------------

``semolina codegen`` takes the view names you want and a ``--backend``, and
writes Python to stdout:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: bash

         semolina codegen analytics.sales --backend snowflake

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: bash

         semolina codegen analytics.sales --backend databricks

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: bash

         semolina codegen sales --backend duckdb --database tutorial.db

Snowflake and Databricks find the view through the credentials in your
``.semolina.toml`` or your environment. DuckDB has no credentials, so it takes
a ``--database`` path instead: ``--backend duckdb`` requires either that flag or
a ``DUCKDB_DATABASE`` environment variable.

Run the DuckDB command and the class arrives on stdout:

.. code-block:: python

   from semolina import Dimension, Fact, Metric, SemanticView


   class Sales(SemanticView, view="sales"):
       country = Dimension[str]()
       region = Dimension[str]()
       revenue = Metric[int | None]()
       cost = Metric[int | None]()

That is the model you wrote by hand in :ref:`tutorial-first-query`, with two
differences. The fields are ordered as the warehouse reports them rather than
as you happened to type them, and each one carries the type its column arrives
as, which you had no way to know without asking.

The ``| None`` on both metrics is not hedging. An aggregate over a group whose
inputs are all NULL returns NULL, so ``SUM`` can produce one whatever the column
underneath allows.

:py:class:`~semolina.fields.Fact` is imported and unused here because this view declares
no facts.
Generated files are meant to be regenerated rather than edited, so codegen emits
one import line for every field type it can produce.

2. Keep it in a file
--------------------

Redirect stdout to write the module. Everything the command has to say for
itself goes to stderr, so the file captures only Python:

.. code-block:: bash

   semolina codegen sales --backend duckdb --database tutorial.db > models.py

Now query with it. The generated ``Sales`` behaves exactly like the hand-written
one, so this is the first-query script with one import changed. Save it as
``check_models.py``:

.. code-block:: python
   :caption: check_models.py

   from adbc_poolhouse import DuckDBConfig

   from models import Sales
   from semolina import create_engine

   create_engine(
       DuckDBConfig(database="tutorial.db"), register=True
   )

   cursor = (
       Sales.query()
       .metrics(Sales.revenue)
       .dimensions(Sales.country)
       .order_by(Sales.revenue.desc())
       .execute()
   )

   for row in cursor.fetchall_rows():
       print(row.country, row.revenue)

.. code-block:: console

   $ python check_models.py
   CA 2000
   US 1500

The typed fields do more than document. ``Metric[int | None]`` is what lets your
editor tell you the type of ``row.revenue`` before you run anything, and what
lets a type checker catch a comparison against the wrong kind of value.

3. Generate the response DTO
----------------------------

``semolina codegen`` describes a view. It cannot describe a *result*, because a
result belongs to one query: it carries the subset of fields that query
projected, under the column names that query produced, with the types that
query's aggregations returned. So the DTO comes from a query instead.

``semolina codegen-dto`` will take a dotted path to a query object you already
wrote. The query in ``reports.py`` is built inside a function, so there is
nothing importable to point at, and the second route fits better: name the view
and the fields and let codegen build the query itself.

This is the projection the dashboard endpoint runs -- the ``revenue`` metric by
the ``country`` dimension:

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: bash

         semolina codegen-dto --backend snowflake \
             --view analytics.sales \
             --metrics revenue --dimensions country \
             --name RevenueByCountry --output dtos.py

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: bash

         semolina codegen-dto --backend databricks \
             --view analytics.sales \
             --metrics revenue --dimensions country \
             --name RevenueByCountry --output dtos.py

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: bash

         semolina codegen-dto --backend duckdb --database tutorial.db \
             --view sales \
             --metrics revenue --dimensions country \
             --name RevenueByCountry --output dtos.py

``--output`` writes the file directly. Without ``--name``, the class would be
called ``Sales`` after the view's last segment.

Run the DuckDB command:

.. code-block:: console

   $ semolina codegen-dto --backend duckdb --database tutorial.db \
       --view sales --metrics revenue --dimensions country \
       --name RevenueByCountry --output dtos.py
   Wrote: dtos.py (1 class)

.. code-block:: python
   :caption: dtos.py

   """
   Generated result DTOs. Do not edit.

   Backend: duckdb

   Column aliases below are the spellings this backend returns for this query, and the
   annotations reflect its own aggregation result typing. Another warehouse needs a
   regenerated class -- these are not portable and are not meant to be.

   Classes:
       RevenueByCountry -- view 'sales' metrics=[revenue] dimensions=[country] (dialect: DuckDBDialect, probe route: execute-schema)
   """

   from __future__ import annotations

   import pydantic


   class RevenueByCountry(pydantic.BaseModel):
       """Result DTO for view 'sales' metrics=[revenue] dimensions=[country] (probe route: execute-schema)."""

       revenue: int | None = pydantic.Field(
           validation_alias="revenue"
       )
       country: str = pydantic.Field(
           validation_alias="country"
       )

No row of your data was fetched. Codegen asked DuckDB to *type* the query rather
than run it, which is what ``probe route: execute-schema`` in the header
records.

The ``validation_alias`` on each field is the payoff. It says which result
column feeds that field, so the field name stays ``revenue`` while the column it
reads is whatever the warehouse called it. Regenerate against Snowflake and the
same file comes back with ``validation_alias='AGG("REVENUE")'`` and
``decimal.Decimal | None``, and the JSON your endpoint returns does not change.

.. warning:: A generated DTO belongs to one backend

   Aliases and annotations are both measured, so a file probed against DuckDB is
   wrong for Snowflake and a file probed against Snowflake is wrong for
   Databricks. The header names the backend that answered. Regenerate against
   the warehouse you deploy to, not the one you develop against.

4. Use both
-----------

``reports.py`` now has nothing left to declare. Delete the hand-written model
and DTO from it and import the generated ones:

.. code-block:: python
   :caption: reports.py

   """Query code the dashboard endpoint calls."""

   from dtos import RevenueByCountry
   from models import Sales


   def revenue_by_country(
       country: str | None = None,
   ) -> list[RevenueByCountry]:
       query = (
           Sales.query()
           .metrics(Sales.revenue)
           .dimensions(Sales.country)
           .where(
               Sales.country == country if country else None
           )
           .order_by(Sales.revenue.desc())
       )
       with query.execute() as cursor:
           return cursor.into(RevenueByCountry)

The test suite from the last tutorial is what tells you the swap worked. Run it
unchanged:

.. code-block:: bash

   pytest

.. code-block:: text

   ============================= test session starts ==============================
   platform darwin -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
   rootdir: /home/you/semolina-tutorial
   plugins: anyio-4.14.2
   collected 3 items

   test_reports.py ...                                                      [100%]

   ============================== 3 passed in 0.18s ===============================

Two generated files, one hand-written query function, and the same three
assertions passing. The projection is the one thing that still has to agree by
hand: ``--metrics revenue --dimensions country`` has to match what the query
selects, or the DTO's aliases will not find their columns.

Next steps
----------

That is the last of the six tutorials. Your application's model, response class and test
suite now all come from the warehouse rather than from memory.

You have generated files that were correct at the moment you generated them.
Both commands take a ``--check`` flag that re-probes the warehouse and exits
non-zero when a committed file no longer matches, which is the thing to put in
CI. See :ref:`howto-codegen-check` and :ref:`howto-dto-codegen`.

Past two or three DTOs, the command line stops being something anyone remembers.
``semolina codegen-dto`` reads a ``[tool.semolina.dto]`` section from
``pyproject.toml``, so the whole set regenerates with a bare
``semolina codegen-dto``. :ref:`howto-dto-codegen` has the format.

Pointing either command at Snowflake or Databricks needs credentials, and
Semolina reads them from ``.semolina.toml``, then the environment, then a
``.env`` file. :ref:`howto-codegen-credentials` covers the chain.

See also
--------

.. grid:: 1 1 2 2
   :class-row: surface
   :gutter: 2

   .. grid-item-card:: Generate models
      :link: howto-codegen
      :link-type: ref

      Multiple views at once, facts, unsupported column types, and what
      introspection reads on each backend.

   .. grid-item-card:: Generate result DTOs
      :link: howto-dto-codegen
      :link-type: ref

      The dotted-path route, ``pyproject.toml`` config, ``Any`` annotations, and
      why every metric is optional.

   .. grid-item-card:: Codegen credentials
      :link: howto-codegen-credentials
      :link-type: ref

      ``.semolina.toml``, environment variables, and ``.env`` files.

   .. grid-item-card:: Check for drift
      :link: howto-codegen-check
      :link-type: ref

      Running ``--check`` in CI so a changed view fails the build.

   .. grid-item-card:: Understanding models
      :link: howto-models
      :link-type: ref

      What the generated field types mean, and the ``source=`` escape hatch for
      a warehouse name Python cannot spell.

   .. grid-item-card:: Type fidelity
      :link: explanation-type-fidelity
      :link-type: ref

      Why the warehouse decides each annotation, and what a generated one
      promises.
