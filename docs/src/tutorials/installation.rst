.. _tutorial-installation:

Installation
============

In this tutorial, you will install Semolina and verify it is working. By the end,
you will be ready to write your first query.

**Prerequisites:** Python 3.11 or later.

Install the package
-------------------

.. tab-set::
   :sync-group: installer

   .. tab-item:: pip
      :sync: pip

      .. code-block:: bash

         pip install semolina

      .. tip:: Use a virtual environment

         Always install packages into an isolated virtual environment rather than
         your system Python:

         .. code-block:: bash

            python -m venv .venv
            source .venv/bin/activate   # macOS/Linux
            .venv\Scripts\activate      # Windows
            pip install semolina

   .. tab-item:: uv
      :sync: uv

      .. code-block:: bash

         uv add semolina

Install a backend extra
-----------------------

To connect to a real warehouse, install the extra for your backend:

.. tab-set::
   :sync-group: backend

   .. tab-item:: Snowflake
      :sync: snowflake

      .. code-block:: bash

         pip install "semolina[snowflake]"
         # or
         uv add "semolina[snowflake]"

      Installs ``adbc-poolhouse[snowflake]`` alongside Semolina.

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: bash

         pip install "semolina[databricks]"
         # or
         uv add "semolina[databricks]"

      Installs ``databricks-sql-connector[pyarrow]`` alongside Semolina.
      The ADBC Databricks driver is **not** on PyPI and no extra can fetch it,
      so add it with the Foundry's CLI:

      .. code-block:: bash

         uv tool install dbc     # or: pipx install dbc
         dbc install databricks

      See :ref:`howto-backends-databricks` for how the driver is found and what
      failure looks like when it is missing.

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: bash

         pip install "semolina[duckdb]"
         # or
         uv add "semolina[duckdb]"

      Installs ``duckdb`` and ``pyarrow`` for local in-memory testing without a warehouse.

   .. tab-item:: Both
      :sync: both

      .. code-block:: bash

         pip install "semolina[snowflake,databricks]"
         # or
         uv add "semolina[snowflake,databricks]"

To follow the tutorials without a real warehouse, install ``semolina[duckdb]`` and
use a local in-memory DuckDB engine. See :ref:`howto-warehouse-testing` for the
setup pattern.

Optional: formatted codegen output
----------------------------------

If you plan to generate model classes from existing warehouse views with
:ref:`semolina codegen <howto-codegen>`, add the ``codegen-lint`` extra. It lets
codegen format the generated source with ruff before printing:

.. code-block:: bash

   pip install "semolina[codegen-lint]"
   # or
   uv add "semolina[codegen-lint]"

Codegen works without it, just without the formatting pass.

Optional: async support
-----------------------

If you query from an async web framework, add the ``async`` extra. It brings in
``adbc-poolhouse``'s async stack, which is what
:py:func:`~semolina.config.create_async_engine` and ``aexecute()`` run on:

.. code-block:: bash

   pip install "semolina[async]"
   # or
   uv add "semolina[async]"

Combine it with your backend extra in one install:

.. code-block:: bash

   pip install "semolina[snowflake,async]"
   # or
   uv add "semolina[snowflake,async]"

A plain ``pip install semolina`` picks up no part of this. The async stack brings an
``anyio`` dependency with it, and Semolina keeps that out of a base install: nothing is
imported until you call an async entry point. The ``all`` extra includes ``async``.

The extra requires ``adbc-poolhouse[async]>=1.6.2``. Earlier releases sized async pools
incorrectly and could deadlock on a cancelled query, so pin no lower.

.. _tutorial-installation-result-extras:

Optional: dataframes and typed results
---------------------------------------

Four extras cover what you can turn a result into. A plain
``pip install semolina`` brings none of them, and each one names the package the
error message will tell you to install if you call the method without it.

**Typed objects.** ``arrowmodel`` is the one to install if you want
:py:meth:`~semolina.cursor.SemolinaCursor.into` and
:py:meth:`~semolina.cursor.SemolinaCursor.iter_into`, which convert a result into
Pydantic instances:

.. code-block:: bash

   pip install "semolina[arrowmodel]"
   # or
   uv add "semolina[arrowmodel]"

It brings ``pyarrow`` along, so this single command is enough. See
:ref:`howto-typed-results`.

**Dataframes.** ``semolina[pandas]`` covers
:py:meth:`~semolina.cursor.SemolinaCursor.fetch_df`, and ``semolina[polars]`` covers
:py:meth:`~semolina.cursor.SemolinaCursor.fetch_polars`:

.. code-block:: bash

   pip install "semolina[pandas]"
   pip install "semolina[polars]"

Each command is enough on its own. ``semolina[pandas]`` pulls ``pyarrow`` in for
you, because ADBC builds a pandas frame through a PyArrow reader.
``semolina[polars]`` does not, because ADBC hands polars the raw Arrow stream
instead, so it stays the smaller install. See :ref:`howto-arrow-output` for both
methods.

**Arrow.** ``pyarrow`` covers
:py:meth:`~semolina.cursor.SemolinaCursor.fetch_arrow_table`,
:py:meth:`~semolina.cursor.SemolinaCursor.fetch_record_batch` and the column types in
``cursor.description``:

.. code-block:: bash

   pip install "semolina[pyarrow]"

Most readers never install it directly. ``semolina[duckdb]`` and
``semolina[arrowmodel]`` both bring it, and one of those is usually already
there.

The ``all`` extra covers all four, alongside ``async`` and every backend.

Each extra sets a minimum version rather than a pin, so a later compatible
release can land in your environment without waiting for a Semolina release:
``pyarrow>=17.0.0``, ``polars>=1.0.0``, ``pandas>=2.0.0``, ``arrowmodel>=1.0.0``.

If you call one of these methods without its extra installed, Semolina raises
:py:exc:`~semolina.exceptions.SemolinaMissingDependencyError` and names the package to
install.

Verify the installation
-----------------------

Run this in your terminal:

.. code-block:: bash

   python -c "import semolina; print(semolina.__version__)"

You should see the version you installed:

.. parsed-literal::

   |release|

If the import fails, double-check that you are in the right virtual environment.

If you installed the ``async`` extra, check that its dependencies resolved too:

.. code-block:: bash

   python -c "from adbc_poolhouse import create_async_pool; print('async support ready')"

You should see:

.. code-block:: text

   async support ready

An ``ImportError`` here means the extra is not installed -- the async stack is resolved
lazily, so ``import semolina`` succeeds either way and does not tell you.

Next steps
----------

Your installation is ready. Move on to writing your first query:

:ref:`Your first query <tutorial-first-query>`

See also
--------

- :ref:`howto-codegen` -- generate Python models from your warehouse schema
- :ref:`howto-backends-overview` -- point the same query code at Snowflake, Databricks
  or DuckDB
- :ref:`howto-web-api` -- serve queries from ``async def`` endpoints, with timeouts and
  cancellation
- :ref:`howto-connection-pools` -- build, size, and dispose sync and async engines
- :ref:`howto-typed-results` -- convert a result into Pydantic instances with
  the ``arrowmodel`` extra
- :ref:`howto-arrow-output` -- Arrow tables and dataframes, and which extra each needs
