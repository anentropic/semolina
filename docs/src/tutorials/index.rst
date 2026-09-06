.. _tutorials:

Tutorials
=========

Six lessons that build one thing. You install Semolina, query a semantic view,
shape the result into a report, serve it from a FastAPI endpoint, put that
endpoint under test, and finish by generating the model and the response class
instead of writing them.

They are meant to be read in order and typed out as you go. Every command and
every block of output on these pages was run against a local DuckDB database
that :ref:`tutorial-first-query` shows you how to build, so you can follow the
whole sequence without a warehouse or a single credential.

When you want more than a lesson gave you, the :ref:`how-to guides <howto-guides>`
go deeper into one part of it at a time.

.. toctree::
   :maxdepth: 1

   installation
   first-query
   shaping-a-report
   dashboard-api
   testing-queries
   warehouse-models
