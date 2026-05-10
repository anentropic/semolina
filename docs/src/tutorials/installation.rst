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

Verify the installation
-----------------------

Run this in your terminal:

.. code-block:: bash

   python -c "import semolina; print(semolina.__version__)"

You should see:

.. code-block:: text

   0.4.0

If the import fails, double-check that you are in the right virtual environment.

Next steps
----------

Your installation is ready. Move on to writing your first query:

:ref:`Your first query <tutorial-first-query>`

See also
--------

- :ref:`howto-codegen` -- generate Python models from your warehouse schema
- :ref:`howto-backends-overview` -- connect to Snowflake or Databricks
