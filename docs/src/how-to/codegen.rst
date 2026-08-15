.. _howto-codegen:

How to generate Semolina model classes from warehouse views
============================================================

Already have a Snowflake semantic view or Databricks metric view set up? ``semolina codegen``
introspects it and prints a Python model class to stdout. You can drop that output straight
into your codebase.

.. tip:: Looking for a result DTO rather than a model class?

   ``semolina codegen`` writes the :py:class:`~semolina.models.SemanticView` class that
   describes a whole view. To generate a Pydantic DTO typed for the columns one *query*
   returns, use ``semolina codegen-dto`` instead. See :ref:`howto-dto-codegen`.

Run codegen
-----------

.. code-block:: bash

   semolina codegen my_schema.sales_view --backend snowflake

That connects to your warehouse, reads the view's column metadata, and prints a ready-to-use
:py:class:`~semolina.models.SemanticView` subclass.

Introspect multiple views at once
---------------------------------

Pass multiple view names in a single call:

.. code-block:: bash

   semolina codegen schema.sales_view schema.orders_view --backend databricks

All classes appear in one output block with a single shared imports section.

Pipe output to a file
---------------------

.. code-block:: bash

   semolina codegen my_schema.sales_view --backend snowflake > models.py

There is no ``--output`` flag; redirect stdout as you would with any CLI tool.

Format the generated output
---------------------------

By default ``semolina codegen`` prints valid but unformatted Python. Install the
optional ``codegen-lint`` extra and codegen runs the generated source through ruff
-- formatting it and sorting imports -- before printing:

.. code-block:: bash

   pip install semolina[codegen-lint]
   # or
   uv add "semolina[codegen-lint]"

Without the extra, codegen still prints the model source to stdout and adds a short
reminder on stderr. The reminder stays out of stdout, so redirecting to a file
(``> models.py``) captures only the Python.

Choose a backend
----------------

Use ``--backend`` (or ``-b``):

.. list-table::
   :header-rows: 1

   * - Value
     - Warehouse
     - Introspects via
   * - ``snowflake``
     - Snowflake semantic views
     - ``SHOW COLUMNS IN VIEW``
   * - ``databricks``
     - Databricks metric views
     - ``DESCRIBE TABLE EXTENDED AS JSON``
   * - ``duckdb``
     - DuckDB semantic views
     - ``DESCRIBE SEMANTIC VIEW``

Credentials come from the ``[connections.<backend>]`` section of
``.semolina.toml``, then from prefixed environment variables (for example
``SNOWFLAKE_ACCOUNT``), then from a ``.env`` file. For DuckDB, pass the database
path with ``--database`` (or set ``DUCKDB_DATABASE``). See
:ref:`howto-codegen-credentials` for the full list of environment variables,
``.env`` file setup, and config file fallback.

.. warning:: Codegen reads a different section from ``create_engine()``

   :py:func:`~semolina.config.create_engine` defaults to ``[connections.default]``.
   ``semolina codegen`` instead reads the section **named after the backend**:
   ``--backend snowflake`` reads ``[connections.snowflake]``, ``--backend databricks``
   reads ``[connections.databricks]``, ``--backend duckdb`` reads
   ``[connections.duckdb]``.

   So a file with only ``[connections.default]`` works for your application and makes
   codegen exit ``2``. Add a section under the backend name as well, or set the
   ``SNOWFLAKE_*`` / ``DATABRICKS_*`` environment variables. See
   :ref:`howto-codegen-credentials`.


Point DuckDB codegen at a database file
---------------------------------------

The DuckDB backend reads a database file on disk, so ``--backend duckdb`` needs a
``--database`` path. You can write that path three ways:

.. code-block:: bash

   semolina codegen sales_view --backend duckdb --database /data/sales.duckdb
   semolina codegen sales_view --backend duckdb --database ./sales.duckdb
   semolina codegen sales_view --backend duckdb --database ~/data/sales.duckdb

A relative path resolves against your current working directory, and a leading
``~`` expands to your home directory. Setting ``DUCKDB_DATABASE`` accepts the same
forms, so you can keep the path out of the command line:

.. code-block:: bash

   export DUCKDB_DATABASE=~/data/sales.duckdb
   semolina codegen sales_view --backend duckdb

Codegen has no in-memory default for DuckDB. If you supply neither ``--database``
nor ``DUCKDB_DATABASE``, the command stops and asks you for a path.

The first run installs the ``semantic_views`` community extension onto the codegen
connection, which needs one-time network access to ``community.duckdb.org``. DuckDB
caches the extension under ``~/.duckdb/extensions/``, so later runs work offline.

Understand the generated output
--------------------------------

.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      Given this semantic view in your warehouse:

      .. code-block:: sql

         CREATE OR REPLACE SEMANTIC VIEW analytics.sales_view
           TABLES (
             s AS source_table PRIMARY KEY (id)
           )
           DIMENSIONS (
             s.country AS country,
             s.unit_price AS unit_price
           )
           METRICS (
             s.revenue AS SUM(s.revenue)
           )
         ;

      Running:

      .. code-block:: bash

         semolina codegen analytics.sales_view --backend snowflake

      Produces:

      .. code-block:: python

         import decimal

         from semolina import Dimension, Fact, Metric, SemanticView


         class SalesView(SemanticView, view="analytics.sales_view"):
             # {"type": "FIXED", "scale": 0}
             revenue = Metric[decimal.Decimal | None]()
             country = Dimension[str]()
             unit_price = Fact[float]()

   .. tab-item:: Databricks
      :sync: databricks

      Given this metric view in your warehouse:

      .. code-block:: sql

         CREATE OR REPLACE VIEW main.analytics.orders_view
           WITH METRICS
           LANGUAGE YAML
           AS $$
             version: 1.1
             source: source_table
             dimensions:
               - name: region
                 expr: region
             measures:
               - name: total_orders
                 expr: COUNT(*)
           $$;

      Running:

      .. code-block:: bash

         semolina codegen main.analytics.orders_view --backend databricks

      Produces:

      .. code-block:: python

         from semolina import Dimension, Fact, Metric, SemanticView


         class OrdersView(
             SemanticView, view="main.analytics.orders_view"
         ):
             total_orders = Metric[int | None]()
             region = Dimension[str]()

   .. tab-item:: DuckDB
      :sync: duckdb

      Given this semantic view in your DuckDB database:

      .. code-block:: sql

         CREATE SEMANTIC VIEW sales_view AS
         TABLES (s AS sales_data PRIMARY KEY (id))
         FACTS (
             s.unit_price AS unit_price
         )
         DIMENSIONS (
             s.country AS country,
             s.region AS region
         )
         METRICS (
             s.revenue AS SUM(s.revenue),
             s.cost AS SUM(s.cost)
         );

      Running:

      .. code-block:: bash

         semolina codegen sales_view --backend duckdb --database ./sales.duckdb

      Produces:

      .. code-block:: python

         from semolina import Dimension, Fact, Metric, SemanticView


         class SalesView(SemanticView, view="sales_view"):
             unit_price = Fact[int]()
             country = Dimension[str]()
             region = Dimension[str]()
             revenue = Metric[int | None]()
             cost = Metric[int | None]()

Every column gets a concrete field type. Codegen reads the role each backend
records for the column and emits the matching ``Metric``, ``Dimension``, or
``Fact``. None of the backends leave a column unclassified, so you never get a
bare ``Field()`` placeholder for a known role.

.. note::

   Databricks metric views model only two roles: measures and dimensions. There
   is no Fact concept, so every non-measure column maps to ``Dimension()``. This
   is intentional, not a missing feature. Snowflake and DuckDB semantic views
   support all three roles (``METRIC``, ``DIMENSION``, ``FACT``), and codegen
   maps each one directly.

Understand field type mapping
-----------------------------

Codegen resolves each backend's native role string to a field type:

.. list-table::
   :header-rows: 1

   * - Warehouse classification
     - Generated field type
   * - Metric / Measure
     - ``Metric[T | None]()``
   * - Dimension
     - ``Dimension[T]()``
   * - Fact (Snowflake and DuckDB)
     - ``Fact[T]()``

Only metrics admit ``None``. A metric is computed over a group, and a group with
nothing to aggregate in it yields a null, so the optional half of the annotation
is the honest one on every backend. Dimensions and facts are columns, and codegen
annotates them with the type the warehouse reports. See
:ref:`explanation-type-fidelity` for the three null cases and why ``COUNT`` is
treated the same way as ``SUM``.

If a backend ever hands back a role string that codegen does not recognize,
generation stops with a ``ValueError`` instead of guessing. A new warehouse
version or a schema change could introduce a role the mapping above doesn't
cover, and silently labelling that column a ``Dimension`` would hide the drift
in your generated model. Failing loudly keeps the generated code honest: you
find out at codegen time, not when a query returns the wrong shape.

Handle TODO comments
--------------------

When a field's SQL type has no clean Python equivalent (GEOGRAPHY, ARRAY, MAP,
STRUCT), codegen types the field as ``Any`` and drops the raw warehouse type into a
TODO comment rather than guessing:

.. code-block:: python

   # TODO: {"type": "GEOGRAPHY"}
   territory = Dimension[Any]()

The comment carries the warehouse's own type descriptor verbatim, so you have the
detail you need to pick a concrete type. ``Any`` keeps the generated module valid in
the meantime; codegen adds ``from typing import Any`` for you whenever a field needs it.

Review these fields after generation and replace ``Any`` with the type you want.

Read a VARIANT column's annotation
----------------------------------

A ``VARIANT`` column no longer lands in the ``Any`` bucket. Codegen annotates it
:py:obj:`~semolina.types.JsonValue`, a recursive union over the whole JSON value domain
(``str | int | float | bool | None``, plus lists and string-keyed dicts of the
same), and adds ``JsonValue`` to the ``from semolina import ...`` line for you:

.. code-block:: python

   from semolina import (
       Dimension,
       Fact,
       JsonValue,
       Metric,
       SemanticView,
   )


   class Events(SemanticView, view="events_view"):
       # VARIANT
       payload = Dimension[JsonValue]()

The union is deliberately loose, because what a driver hands over for a semi-structured
column is not settled. On Databricks a ``variant`` value arrives as JSON **text**, so
you get a ``str`` and parse it yourself rather than a ready-made ``dict``. ``JsonValue``
is correct either way, which is why it is a union rather than ``dict[str, Any]``.

Read the raw warehouse type from a field comment
------------------------------------------------

The ``TODO:`` comment above is not the only comment codegen writes. Whenever a
field's annotation does not name its warehouse type, codegen emits that type on
its own line above the field, so the detail survives even though the annotation
is concrete:

.. code-block:: python

   # DECIMAL(10,2)
   max_order_value = Metric[decimal.Decimal | None]()

   # {"type": "FIXED", "scale": 0}
   revenue = Metric[decimal.Decimal | None]()

A ``DECIMAL(10,2)`` and a ``DECIMAL(38,2)`` both annotate
:py:class:`decimal.Decimal`, so without the comment the precision and scale would
be gone from your model. The same applies to a ``UUID``, a ``JSON`` column, or an
``ENUM``: each annotates ``str``, because a ``str`` is what the driver hands over,
and the comment is where the original type name lives.

.. _howto-codegen-check:

Check a committed model for drift
---------------------------------

Once a model is in your codebase, ``--check`` reports whether its annotations still
describe what the warehouse returns:

.. code-block:: bash

   semolina codegen sales_view \
       --check --model path/to/models.py \
       --backend duckdb --database ./analytics.db

Pass ``--model`` alongside ``--check``: it names the committed file to read. Either
flag on its own exits ``2``. Credentials come from the environment exactly as they do
for generation, so nothing secret belongs on this command line.

The run writes nothing to stdout. One table per view goes to stderr:

.. code-block:: text

   semolina codegen --check: sales_view
   ┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┓
   ┃ Field      ┃ Committed         ┃ Probed (result    ┃ Route          ┃ Status ┃
   ┃            ┃                   ┃ schema)           ┃                ┃        ┃
   ┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━┩
   │ unit_price │ int               │ int               │ execute-schema │ match  │
   │ country    │ str               │ str               │ execute-schema │ match  │
   │ region     │ str               │ str               │ execute-schema │ match  │
   │ revenue    │ decimal.Decimal | │ int | None        │ execute-schema │ drift  │
   │            │ None              │                   │                │        │
   │ cost       │ int | None        │ int | None        │ execute-schema │ match  │
   └────────────┴───────────────────┴───────────────────┴────────────────┴────────┘

The comparison is per field, and the right-hand side is the **result schema** of a
query against the view: the types the warehouse says it would return. It is not a
regenerated model diffed against yours, so reformatting your file, reordering fields,
or renaming the class changes nothing. Only an annotation moves a row to ``drift``.

No row of your data is fetched. The check reads the view's catalogue entry and asks
the warehouse to type a query, which is why it is cheap enough to put in CI.

Read the route on every row
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``Route`` column names where each probed type came from, so a green check can
never quietly mean "I could not ask, so I compared against the catalogue instead":

.. list-table::
   :header-rows: 1

   * - Route
     - What happened
   * - ``execute-schema``
     - The driver answered a describe-only call. No query ran.
   * - ``zero-row``
     - The driver has no describe-only call, so the query ran wrapped to return no rows.
   * - ``metadata``
     - Neither route was open, so the annotation was compared against the warehouse
       catalogue. A note on stderr says why.
   * - ``not-probed``
     - Your model declares a field the view does not have, so no query looked at it.
       The ``Probed`` column reads ``(absent)``.

A ``metadata`` row is a weaker answer than the other two, because the catalogue is
the source ``codegen`` already used. Comparing a model against the source that wrote
it can only ever agree with itself.

A view that needs more than one query gets a route per query, not one for the run:
DuckDB cannot select facts and metrics in a single ``semantic_view()`` call, and a
driver is free to answer one query and refuse the other.

Read the Detail lines
~~~~~~~~~~~~~~~~~~~~~

Two kinds of drift do not show up in the ``Committed`` and ``Probed`` columns, because
both sides still read the same annotation:

- the field's **role** changed. A ``Metric`` committed as a ``Dimension`` lands in the
  wrong ``semantic_view()`` clause.
- the field's **column** changed. A ``source=`` naming a column the warehouse has since
  renamed makes every query select something that is not there.

Both move the row to ``drift`` and print a line under the table naming what moved:

.. code-block:: text

   Detail: revenue: role: committed Dimension, warehouse Metric
   Detail: country: column: committed 'OLD_NAME', warehouse 'NEW_NAME'

The column comparison is on the name the query will actually use, so adding
``source="COUNTRY"`` to a field the dialect already resolves to ``COUNTRY`` is not drift.

A ``Detail`` line also appears when the result schema came back carrying two columns of
the same name. That one is about the warehouse rather than your model: ``--check`` cannot
say which column the field is, so it reports ``Any`` and tells you why.

Interpret the exit code
~~~~~~~~~~~~~~~~~~~~~~~

``0`` means every annotation matched. ``5`` means at least one drifted. A missing or
unparseable ``--model`` file exits ``1``, and a bad flag pairing exits ``2``, which is
why drift has a code of its own rather than sharing ``1``.

Drift is worth reading before you act on it. ``semolina codegen`` builds a model from
the catalogue while ``--check`` prefers the result schema, so the two can disagree on
a model that was generated moments earlier. See :ref:`explanation-type-fidelity` for
why the two sources differ and which one to believe.

.. warning::

   ``--check`` is confirmed against Snowflake and DuckDB. On Databricks it is
   **unverified**, because that driver answers no describe-only call and the
   zero-row route has not yet been confirmed against a live metric view. Treat a
   Databricks ``--check`` result as unconfirmed in either direction for now.

Exit codes
----------

``semolina codegen`` uses distinct exit codes so scripts can handle each failure mode separately:

.. list-table::
   :header-rows: 1

   * - Exit code
     - Meaning
   * - ``0``
     - Success -- model class written to stdout
   * - ``1``
     - Unexpected error (see stderr for details), including a missing or
       unparseable ``--model`` file
   * - ``2``
     - Invalid option -- an unrecognized or omitted ``--backend``, connection
       config that could not be assembled, ``--backend duckdb`` with no database
       path, or ``--check`` and ``--model`` passed without each other
   * - ``3``
     - View not found -- the warehouse has no semantic view with that name
   * - ``4``
     - Connection failure -- credentials missing or authentication rejected
   * - ``5``
     - Annotation drift -- a committed model no longer matches the result schema

.. tip::

   Exit code 2 is also what the CLI argument parser emits when ``--backend`` is
   omitted entirely, so a script cannot tell a missing backend from a rejected value
   or a bad flag pairing. Read stderr for which option it was.

.. tip::

   Exit 5 means the tool worked and found drift; exit 1 means the tool broke. They
   are separate codes so a CI job can fail a build on a stale model without also
   failing it on a crash, or the reverse.

Override the SQL column name with source=
-----------------------------------------

By default, Semolina maps Python field names to SQL column names using each dialect's
identifier casing rules (Snowflake uppercases unquoted identifiers; Databricks lowercases them).
For a field ``order_id``, Snowflake resolves ``ORDER_ID`` automatically.

If your warehouse stores a column with non-default casing, for example a quoted
lowercase column ``"order_id"`` in Snowflake, you can override the SQL column name
with ``source=``:

.. code-block:: python

   class Orders(SemanticView, view="orders"):
       order_id = Metric[int](
           source="order_id"
       )  # maps to quoted "order_id", not "ORDER_ID"

``semolina codegen`` emits ``source=`` automatically when introspection detects that a column
uses non-default casing.

See also
--------

- :ref:`howto-dto-codegen` -- generating a result DTO for one query instead of a
  model class for a whole view
- :ref:`explanation-type-fidelity` -- why the catalogue and the result schema
  disagree, and what a generated annotation promises
- :ref:`howto-codegen-credentials` -- environment variables, .env files, and config file fallback
- :ref:`reference-cli` -- every flag, argument, and exit code
- :ref:`howto-models` -- model class structure and field types
- :ref:`howto-backends-snowflake` -- Snowflake pool configuration
- :ref:`howto-backends-databricks` -- Databricks pool configuration
- :ref:`howto-backends-duckdb` -- DuckDB pool configuration
