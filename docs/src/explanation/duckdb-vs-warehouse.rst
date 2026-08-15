.. _explanation-duckdb-vs-warehouse:

Developing on DuckDB, deploying elsewhere
=========================================

DuckDB is the backend you can run on a laptop. It needs no credentials, it starts in
memory, no query costs you anything, and a test suite can hold a whole semantic view
in a fixture. So it is where most Semolina code gets written first, and
:ref:`howto-warehouse-testing` builds a test fixture around exactly that.

It is also the most forgiving of the three backends, which is a problem only when it is
the only one you ever run against. The failure mode is specific: your code works locally,
your tests pass in CI, and it breaks the first time it talks to Snowflake. Nothing in
between catches it, because the thing that differs is the shape of the *result*, and a
DuckDB-only test suite only ever sees DuckDB's shape. This page is about what actually
differs, what has been measured, and what has not.

The same query, three sets of column names
------------------------------------------

Your warehouse names each result column after the expression it computed. There is no
step where Semolina renames anything: it emits no ``AS`` aliases, and a
:py:class:`~semolina.results.Row` takes its keys verbatim from the driver's
``cursor.description``, with no case folding and no punctuation stripping.

Two independent decisions inside the warehouse produce the name. It wraps a metric in
whatever function its dialect uses to evaluate one, and it folds unquoted identifiers to
its preferred case. Take ``Sales.query().metrics(Sales.revenue).dimensions(Sales.country)``:

.. list-table::
   :header-rows: 1
   :widths: 20 25 25 30

   * - Backend
     - Metric wrapper
     - Identifier folding
     - Result column keys
   * - Snowflake
     - ``AGG()``
     - upper case
     - ``AGG("REVENUE")``, ``COUNTRY``
   * - Databricks
     - ``MEASURE()``
     - lower case
     - ``measure(revenue)``, ``country``
   * - DuckDB
     - none
     - lower case
     - ``revenue``, ``country``

DuckDB is the outlier because its ``semantic_view()`` table function does the aggregation
inside itself, so there is no wrapper call left in the projection to name the column
after. A metric comes back under its own name, spelled like a Python identifier by
coincidence rather than by design.

That coincidence is what makes attribute access look portable when it is not:

.. code-block:: python

   with Sales.query().metrics(Sales.revenue).dimensions(
       Sales.country
   ).execute() as cursor:
       row = cursor.fetchone_row()

   row.revenue  # DuckDB. On Snowflake: AttributeError
   row['AGG("REVENUE")']  # Snowflake. On DuckDB: KeyError

Every worked example that reads a result by attribute is therefore a DuckDB example,
whether or not it says so. :ref:`howto-result-column-names` is the authority on what to
write instead, and it is the section to read before your code meets a real warehouse.

Decimals are not a DuckDB difference
------------------------------------

This one looks like the same story and is not, which is why it is worth stating
separately. A ``DECIMAL`` column arrives as a :py:class:`decimal.Decimal` on DuckDB and
on Snowflake -- both measured, the Snowflake observation coming from a recorded
``decimal128(38, 0)`` result. The conversion happens in Arrow rather than in any one
driver, so there is no reason to expect Databricks to differ, but its recorded fixture
declares an integer revenue column, so that particular observation is missing. Treat a
decimal metric as arriving as a ``Decimal`` everywhere: ``json.dumps`` on a row holding
one raises ``TypeError`` on your laptop as readily as in production.

What makes it *look* DuckDB-specific is the sample data. The database the tutorial builds
declares ``revenue`` as an ``INTEGER``, so nothing computed over it is ever a
``Decimal``, and serialization code written against those examples has never met the
type it will meet against your warehouse. The forgiving thing is the fixture, not the
engine.

So switching to Snowflake will not introduce this bug and staying on DuckDB will not
protect you from it. What surfaces it is a decimal column, whichever backend holds one.
:ref:`explanation-type-fidelity` covers which columns arrive as a ``Decimal`` and why the
warehouse rather than Semolina decides that; :ref:`howto-serialization` covers the
encoder to give ``json.dumps``.

Driver errors, mostly unmeasured
--------------------------------

When a query fails, what reaches your handler is the ADBC driver's own exception,
re-raised unchanged. Which subclass you get is the driver's decision, and the names do
not mean what they sound like. Measured against DuckDB, a missing view or table, invalid
SQL syntax, and a reference to a column that does not exist all raise
``adbc_driver_manager.InternalError``. A value that fails to cast raises
``ProgrammingError`` instead. Nothing about "internal" describes a typo in a view name.

Snowflake and Databricks have not been measured. The recorded cassettes the test suite
replays contain only successful queries, so there is no observation of what either driver
raises for any of those four failures, and guessing from the DuckDB result would be
guessing twice: once about the driver, once about the warehouse behind it.

The honest position is that error classification is per-driver knowledge you acquire by
watching your own driver, and that a handler written against DuckDB's classification is
a handler written against one measurement. The "Handle errors" section of
:ref:`howto-web-api` has the table and the shape of a handler that does not depend on it.

Why Semolina does not smooth this over
--------------------------------------

You could imagine Semolina normalising all of this: aliasing every projected column back
to its model field name, casting decimals to floats, mapping driver exceptions onto its
own hierarchy. It does none of the three, and the omission is the same decision made
three times.

What comes back from a query is what the warehouse and its driver produced. Aliasing
would mean Semolina choosing names your warehouse did not use, which makes generated SQL
harder to compare against SQL you wrote by hand and hides a real difference between
backends behind a name that is the same everywhere. Casting decimals would mean rounding
your revenue on the way past. Wrapping exceptions would mean Semolina's guess about a
failure standing between you and the driver's message, which is where the detail
actually lives.

The cost lands on you as portability work, and this page exists because that cost is
easy to defer until deployment day. The benefit is that nothing arrives renamed,
rounded, or reclassified, and that what you debug is what the warehouse said.

Working across the gap
----------------------

None of this makes DuckDB the wrong place to develop. It makes DuckDB the wrong place to
*validate* the half of your code that reads results.

A DuckDB test proves the parts that are genuinely backend-independent: that your query
builder emits the query you meant, that your filters narrow what you expected, that your
aggregation logic is right. It proves nothing about column names, and it cannot fail on a
decimal your sample data does not contain. Treat a green DuckDB suite as evidence about
query construction and as silence about result handling.

Result-reading code is the part to write against the warehouse you deploy to, from the
first line rather than at the end. Converting into typed objects with
:py:meth:`~semolina.cursor.SemolinaCursor.into` and declaring each column's real name
with ``validation_alias`` is the portable form of this, because the warehouse's spelling
lives in one declaration per field instead of scattered across every attribute access.
:ref:`howto-typed-results` covers it.

You do not need a connection to find out what the other backends would be sent.
``.to_sql(dialect=...)`` renders a query for any dialect from your laptop, which is the
cheapest way to see how a metric will be wrapped and how identifiers will be folded
before you have credentials for anything. See :ref:`howto-inspect-sql`.

When you want tests that assert against real warehouse behaviour, the route is to record
it once rather than to approximate it. ``pytest-adbc-replay`` captures the real Arrow
results from a credentialed run into a cassette and replays them offline afterwards, so
the column names and column types your assertions see are the ones your warehouse
produced. :ref:`howto-warehouse-testing` covers recording and replay.

See also
--------

- :ref:`explanation-type-fidelity` -- why money arrives as a ``Decimal`` and what the
  warehouse decides about metric types
- :ref:`howto-result-column-names` -- the column names each backend returns, and the
  aliases to declare for them
- :ref:`howto-typed-results` -- convert a result into Pydantic instances with
  :py:meth:`~semolina.cursor.SemolinaCursor.into`
- :ref:`howto-serialization` -- encoders for ``json.dumps``, and the untyped route to a
  response body
- :ref:`howto-inspect-sql` -- render a query for another dialect without executing it
- :ref:`howto-warehouse-testing` -- the DuckDB fixture, and recording your warehouse with
  ``pytest-adbc-replay``
- :ref:`howto-web-api` -- error handling in a request handler, including the measured
  driver exception table
- :ref:`explanation-semantic-views` -- how the three warehouses implement semantic views
