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

         pip install semolina[snowflake]
         # or
         uv add "semolina[snowflake]"

      Installs ``adbc-poolhouse[snowflake]`` alongside Semolina.

   .. tab-item:: Databricks
      :sync: databricks

      .. code-block:: bash

         pip install semolina[databricks]
         # or
         uv add "semolina[databricks]"

      Installs ``adbc-poolhouse[databricks]`` alongside Semolina.

   .. tab-item:: DuckDB
      :sync: duckdb

      .. code-block:: bash

         pip install semolina[duckdb]
         # or
         uv add "semolina[duckdb]"

      Installs ``duckdb`` and ``pyarrow`` for local in-memory testing without a warehouse.

   .. tab-item:: Both
      :sync: both

      .. code-block:: bash

         pip install semolina[snowflake,databricks]
         # or
         uv add "semolina[snowflake,databricks]"

To follow the tutorials without a real warehouse, install ``semolina[duckdb]`` and
use a local in-memory DuckDB pool. See :ref:`howto-warehouse-testing` for the
setup pattern.

Optional: formatted codegen output
----------------------------------

If you plan to generate model classes from existing warehouse views with
:ref:`semolina codegen <howto-codegen>`, add the ``codegen-lint`` extra. It lets
codegen format the generated source with ruff before printing:

.. code-block:: bash

   pip install semolina[codegen-lint]
   # or
   uv add "semolina[codegen-lint]"

Codegen works without it, just without the formatting pass.

Optional: async support
-----------------------

If you query from an async web framework, add the ``async`` extra. It brings in
``adbc-poolhouse``'s async stack, which is what
:py:func:`~semolina.create_async_engine` and ``aexecute()`` run on:

.. code-block:: bash

   pip install semolina[async]
   # or
   uv add "semolina[async]"

Combine it with your backend extra in one install:

.. code-block:: bash

   pip install "semolina[snowflake,async]"
   # or
   uv add "semolina[snowflake,async]"

A plain ``pip install semolina`` picks up no part of this. The async stack brings an
``anyio`` dependency with it, and Semolina keeps that out of a base install: nothing is
imported until you call an async entry point. The ``all`` extra includes ``async``
along with every backend.

The extra pins ``adbc-poolhouse[async]>=1.6.1``. The floor is that release rather than
an earlier one because ``create_async_pool`` ignored the config's own ``pool_size``
before 1.6.0 and always built a pool of five. Under that behaviour a
``DuckDBConfig(database=":memory:", pool_size=1)`` would silently get five isolated
in-memory databases, each connection seeing a different empty one.

Verify the installation
-----------------------

Run this in your terminal:

.. code-block:: bash

   python -c "import semolina; print(semolina.__version__)"

You should see:

.. code-block:: text

   0.6.0

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
- :ref:`howto-backends-overview` -- connect to Snowflake or Databricks
- :ref:`howto-web-api` -- serve queries from sync or ``async def`` endpoints
- :ref:`howto-connection-pools` -- build, size, and dispose sync and async engines
