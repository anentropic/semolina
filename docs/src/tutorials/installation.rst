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

   .. tab-item:: Both
      :sync: both

      .. code-block:: bash

         pip install semolina[snowflake,databricks]
         # or
         uv add "semolina[snowflake,databricks]"

You do not need a backend extra to follow the tutorials. The built-in
:py:class:`~semolina.MockPool` works without any additional packages.

Verify the installation
-----------------------

Run this in your terminal:

.. code-block:: bash

   python -c "import semolina; print(semolina.__version__)"

You should see:

.. code-block:: text

   0.1.0

If the import fails, double-check that you are in the right virtual environment.

Next steps
----------

Your installation is ready. Move on to writing your first query:

:doc:`Your first query <first-query>`

See also
--------

- :doc:`../how-to/codegen` -- generate Python models from your warehouse schema
- :doc:`../how-to/backends/overview` -- connect to Snowflake or Databricks
