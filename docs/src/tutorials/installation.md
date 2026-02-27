# Installation

In this tutorial, you'll install Semolina and verify it's working. By the end,
you'll be ready to write your first query.

**Prerequisites:** Python 3.11 or later.

## Install the package

=== "pip"

    ```bash
    pip install semolina
    ```

    !!! tip "Use a virtual environment"
        Always install packages into an isolated virtual environment rather than your system Python:

        ```bash
        python -m venv .venv
        source .venv/bin/activate   # macOS/Linux
        .venv\Scripts\activate      # Windows
        pip install semolina
        ```

=== "uv"

    ```bash
    uv add semolina
    ```

## Install a backend extra

To connect to a real warehouse, install the extra for your backend:

=== "Snowflake"

    ```bash
    pip install semolina[snowflake]
    # or
    uv add "semolina[snowflake]"
    ```

    Installs `snowflake-connector-python` alongside Semolina.

=== "Databricks"

    ```bash
    pip install semolina[databricks]
    # or
    uv add "semolina[databricks]"
    ```

    Installs `databricks-sql-connector` alongside Semolina.

=== "Both"

    ```bash
    pip install semolina[snowflake,databricks]
    # or
    uv add "semolina[snowflake,databricks]"
    ```

You don't need a backend extra to follow the tutorials. The built-in `MockEngine`
works without any additional packages.

## Verify the installation

Run this in your terminal:

```bash
python -c "import semolina; print(semolina.__version__)"
```

You should see:

```
0.1.0
```

If the import fails, double-check that you're in the right virtual environment.

## Next steps

Your installation is ready. Move on to writing your first query:

[Your first query :octicons-arrow-right-24:](first-query.md){ .md-button .md-button--primary }

## See also

- [Codegen CLI](../how-to/codegen.md) -- generate Python models from your warehouse schema
- [Backends overview](../how-to/backends/overview.md) -- connect to Snowflake or Databricks
