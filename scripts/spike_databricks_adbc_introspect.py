#!/usr/bin/env python
"""
Standalone spike: validate Databricks metric-view introspection over ADBC.

This is a one-off validation tool (NOT a pytest test, NOT a recorded cassette).
It runs ``DESCRIBE TABLE EXTENDED {view} AS JSON`` two ways against a *live*
Databricks SQL Warehouse and asserts the single-cell JSON results are
structurally identical:

1. ADBC path  -- via ``create_engine(warehouse_config("databricks"))``, the same
   pooled ADBC connection the production ``DatabricksEngine`` uses.
2. Native path -- via ``databricks.sql.connect`` (the pre-Phase-44 connector).

Why this exists
---------------
The Foundry-distributed Databricks ADBC driver (``adbc_driver_databricks``) is
NOT on PyPI and is not installed in the dev/CI venv, and the Databricks
recording hangs on warehouse cold-start. So Databricks ADBC introspection has
never actually been run. ``DatabricksEngine.introspect()`` ships a marked
``NotImplementedError`` fallback until this spike is run successfully against a
live warehouse with the Foundry driver installed (see Phase 44 / 44-RESEARCH.md).

How to run (operator, later)
----------------------------
1. Install the Foundry Databricks ADBC driver into this venv (ADBC Driver
   Foundry / Columnar -- not PyPI).
2. Start a SQL Warehouse with at least one metric view to introspect.
3. Provide credentials either via ``[connections.databricks]`` in
   ``.semolina.toml`` or the ``DATABRICKS_HOST`` / ``DATABRICKS_HTTP_PATH`` /
   ``DATABRICKS_TOKEN`` environment variables.
4. Run::

       python scripts/spike_databricks_adbc_introspect.py <schema.metric_view>

The script FAILS FAST with a clear message (exit code 2) when the Foundry ADBC
driver is absent, and (exit code 2) when credentials are missing -- it never
hangs on a cold-start connect. It never prints the access token: the config is
built via ``warehouse_config`` (the token stays a wrapped ``SecretStr``) and
only the compared JSON column metadata is printed.

This spike deliberately does NOT use ``pytest-adbc-replay`` -- it decouples
introspection validation from the recording hang (44-RESEARCH Open Q3).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# Exit codes the operator / checkpoint can key off of.
_EXIT_OK = 0
_EXIT_MISMATCH = 1
_EXIT_PRECONDITION = 2  # missing Foundry driver or missing credentials


def _describe_sql(view_name: str) -> str:
    """Return the introspection statement (identical for both paths)."""
    return f"DESCRIBE TABLE EXTENDED {view_name} AS JSON"


def _normalize_columns(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Reduce a DESCRIBE-TABLE-EXTENDED JSON payload to the comparable fields.

    Keeps only the structural metadata the introspector relies on -- column
    name, ``is_measure`` flag, type name, and comment -- so ADBC and native
    results can be compared without spurious ordering/whitespace differences.
    """
    out: list[dict[str, Any]] = []
    for col in schema.get("columns", []):
        type_obj: Any = col.get("type", {})
        type_name = type_obj.get("name") if isinstance(type_obj, dict) else str(type_obj)
        out.append(
            {
                "name": str(col.get("name", "")),
                "is_measure": bool(col.get("is_measure", False)),
                "type": type_name,
                "comment": str(col.get("comment") or ""),
            }
        )
    out.sort(key=lambda c: c["name"])
    return out


def _run_adbc(view_name: str) -> list[dict[str, Any]]:
    """
    Run the introspection SQL over the engine's owned ADBC pool.

    Builds the Databricks ADBC pool exactly as production does
    (``create_engine(warehouse_config("databricks"))``) and runs the DESCRIBE
    over ``engine.connect()``. Raises ``ImportError`` (surfaced by the caller as
    a precondition failure) when the Foundry ADBC driver is not installed.
    """
    from semolina.config import create_engine, warehouse_config

    engine = create_engine(warehouse_config("databricks"))
    with engine.connect() as conn:
        cur = conn.cursor()
        cur.execute(_describe_sql(view_name))
        row: Any = cur.fetchone()
    schema: dict[str, Any] = json.loads(row[0])
    return _normalize_columns(schema)


def _run_native(view_name: str) -> list[dict[str, Any]]:
    """
    Run the same introspection SQL via the native ``databricks.sql`` connector.

    Reads the same credentials ``warehouse_config`` resolves, unwrapping the
    token only at the connect boundary (never printed). Provides the comparison
    baseline for the ADBC result.
    """
    import databricks.sql  # noqa: PLC0415  (lazy: only needed on the native path)

    from semolina.config import warehouse_config

    config = warehouse_config("databricks")
    token_attr: Any = getattr(config, "token", None)
    access_token = (
        token_attr.get_secret_value() if hasattr(token_attr, "get_secret_value") else token_attr
    )
    with (
        databricks.sql.connect(
            server_hostname=getattr(config, "host", None),
            http_path=getattr(config, "http_path", None),
            access_token=access_token,
        ) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(_describe_sql(view_name))
        row: Any = cur.fetchone()
    schema: dict[str, Any] = json.loads(row[0])
    return _normalize_columns(schema)


def main(argv: list[str] | None = None) -> int:
    """
    Compare ADBC vs native Databricks introspection for one metric view.

    Returns an exit code: 0 (structurally identical), 1 (mismatch), or 2
    (precondition failure -- Foundry driver or credentials absent).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "view_name",
        help="Databricks metric view to introspect (e.g. schema.metric_view).",
    )
    args = parser.parse_args(argv)
    view_name: str = args.view_name

    # --- ADBC path (fails fast if the Foundry driver is absent) ---
    try:
        adbc_cols = _run_adbc(view_name)
    except ImportError as e:
        # poolhouse raises ImportError ("ADBC driver 'databricks' not found")
        # when the Foundry-distributed driver is not installed.
        print(
            "PRECONDITION FAILED: the Foundry Databricks ADBC driver is not installed.\n"
            f"  ({type(e).__name__}: {e})\n"
            "  Install the Foundry/Columnar Databricks ADBC driver into this venv, then "
            "re-run this spike.",
            file=sys.stderr,
        )
        return _EXIT_PRECONDITION
    except Exception as e:  # noqa: BLE001  (spike: any other failure is a precondition issue)
        print(
            "PRECONDITION FAILED: could not build/run the Databricks ADBC path.\n"
            f"  ({type(e).__name__}: {e})\n"
            "  Check credentials (.semolina.toml [connections.databricks] or DATABRICKS_* env) "
            "and that a SQL Warehouse is running.",
            file=sys.stderr,
        )
        return _EXIT_PRECONDITION

    # --- Native path (comparison baseline) ---
    try:
        native_cols = _run_native(view_name)
    except ImportError as e:
        print(
            "PRECONDITION FAILED: the native databricks-sql-connector is not installed.\n"
            f"  ({type(e).__name__}: {e})\n"
            "  Install it with: pip install semolina[databricks]",
            file=sys.stderr,
        )
        return _EXIT_PRECONDITION
    except Exception as e:  # noqa: BLE001  (spike: surface any native failure clearly)
        print(
            "PRECONDITION FAILED: could not run the native databricks.sql path.\n"
            f"  ({type(e).__name__}: {e})",
            file=sys.stderr,
        )
        return _EXIT_PRECONDITION

    # --- Compare (token never printed; only structural column metadata) ---
    print(f"view: {view_name}")
    print(f"ADBC columns   ({len(adbc_cols)}): {json.dumps(adbc_cols, indent=2)}")
    print(f"native columns ({len(native_cols)}): {json.dumps(native_cols, indent=2)}")

    if adbc_cols == native_cols:
        print(
            "\nRESULT: ADBC and native DESCRIBE TABLE EXTENDED AS JSON are "
            "STRUCTURALLY IDENTICAL (same columns, is_measure flags, types, comments)."
        )
        return _EXIT_OK

    print(
        "\nRESULT: MISMATCH between ADBC and native introspection -- investigate before "
        "wiring the real ADBC path.",
        file=sys.stderr,
    )
    return _EXIT_MISMATCH


if __name__ == "__main__":
    raise SystemExit(main())
