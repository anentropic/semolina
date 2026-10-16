Changelog
=========

What changed in each Semolina release. The full history of earlier releases is on the
`GitHub releases page <https://github.com/s-layer/semolina/releases>`_.

0.7.0 (unreleased)
------------------

0.7.0 adds an async query surface and typed results. It also fixes several 0.6 queries
that ran without complaint and returned the wrong rows. Read the first two sections before
you upgrade from 0.6.

Changes that need action
~~~~~~~~~~~~~~~~~~~~~~~~

**The** ``semolina`` **command needs the** ``[cli]`` **extra.** typer, rich and jinja2 are
no longer base dependencies, so ``pip install semolina`` no longer installs what
``semolina codegen`` and ``semolina codegen-dto`` need. griffelib, which is new in 0.7 and
reads committed files for ``--check``, is in the extra too. Install the command with:

.. code-block:: shell

   pip install "semolina[cli]"

Without the extra, ``semolina`` prints that line and exits with code 2. A service that
only runs queries no longer installs the command's packages, and ``import semolina`` no
longer imports pydantic-settings or SQLAlchemy until you call ``create_engine``.

**The SQL-generation base class is** ``SQLDialect``. Only one thing in Semolina is now
called ``Dialect``: the enum you pass to ``to_sql()``. If you subclassed the base class
through ``semolina.engines.sql.Dialect`` or ``semolina.engines.DialectABC``, rename it.
Both old names still work in 0.7 with a ``DeprecationWarning``.

**Result columns are named after your fields on every warehouse.** Semolina now aliases
each selected column to its Python field name, so ``row.revenue`` works on Snowflake,
Databricks and DuckDB alike. In 0.6 the same query returned ``AGG("REVENUE")`` on
Snowflake and ``measure(revenue)`` on Databricks. If your code read those keys, read
the field names instead.

**A filter given** ``None`` **raises** ``TypeError``. In 0.6 a filter such as
``Sales.revenue >= None`` compiled to a comparison with ``NULL``, which matches no row,
so the query quietly came back empty. Now every comparison and lookup refuses ``None``
when you build it, and so does a ``None`` inside ``in_()``. ``==`` and ``!=`` are the
exception (see below). If your code passes an optional parameter straight into a filter,
leave the filter out when the value is ``None``, or use ``.isnull()`` if you meant to
match missing values.

Fixed
~~~~~

Each of these ran without an error in 0.6 and returned the wrong result. 0.7 either
returns the right rows or refuses the query with an exception.

- ``in_()`` given a string, such as ``Sales.country.in_("US")``, treated each character
  as a separate value. It now raises ``TypeError``. It also accepts a generator, and the SQL always
  has as many placeholders as there are values.
- ``field == None`` and ``field != None`` compiled to ``= NULL`` and ``<> NULL``, which
  match nothing. They now compile to ``IS NULL`` and ``IS NOT NULL``. Every other
  comparison or lookup given ``None``, ``between()`` and a ``None`` inside ``in_()``
  among them, raises ``TypeError`` and points you at ``.isnull()``.
- ``startswith``, ``istartswith``, ``endswith``, ``iendswith`` and ``iexact`` treated
  ``%`` and ``_`` in your value as wildcards. They now match them literally on every
  dialect. ``like`` and ``ilike`` still pass your pattern through as written.
- A result with two columns of the same name, which selecting one field twice produces,
  silently kept the last value. Selecting a field twice now raises ``ValueError`` in the
  builder, and a ``Row`` refuses duplicate column names.
- On DuckDB, a query that selects facts and no metric returned one row per source row,
  where Snowflake and Databricks group the same query. DuckDB now returns each distinct
  row once too.

Changed
~~~~~~~

- ``to_sql()`` with no argument previews the dialect of the engine ``.using()`` names,
  when that engine is registered. Without ``.using()``, it still previews Snowflake.
- Every exception class Semolina defines derives from ``SemolinaError``, so one
  ``except`` clause can catch them all. Each keeps its 0.6 base class, so existing
  ``except RuntimeError`` and ``except ValueError`` clauses still match. Looking up an
  engine that was never registered raises ``SemolinaEngineNotRegisteredError``, which is
  still a ``ValueError``.
- ``introspect()``, and so ``semolina codegen``, reports a view the warehouse reached but
  could not describe, such as one whose definition no longer binds, as the new
  ``SemolinaIntrospectionError`` rather than ``SemolinaConnectionError``, and
  ``semolina codegen`` exits 6 for it rather than 4. Connection and authentication
  failures still raise ``SemolinaConnectionError``.
- ``Query`` is public, and ``Field``, ``Engine``, ``AsyncEngine``, ``And``, ``Or``,
  ``Not`` and ``Lookup`` are importable from ``semolina``. The query builder's methods
  are typed, so a type checker flags ``.metrics(Sales.country)`` or ``.limit("10")``.

Added
~~~~~

- ``aexecute()`` and async row streaming, under asyncio or Trio, with the ``[async]``
  extra. Cancelling a query stops it inside the driver.
- ``.into(Model)`` turns a result into Pydantic models, and ``fetch_df()`` and
  ``fetch_polars()`` return a pandas or Polars DataFrame.
- ``semolina codegen-dto`` writes the Pydantic model for a query's result, typed from
  the warehouse's own result schema.
- ``semolina codegen --check`` reports where your models no longer match the warehouse,
  and ``--output`` writes the generated module to a file.

See also
--------

- :doc:`/tutorials/installation` covers the extras, ``[cli]`` among them.
- :doc:`/how-to/web-api` shows how to catch ``SemolinaError`` in a request handler.
- :doc:`/how-to/filtering` covers filters, including ``None`` and the string lookups.
