"""
Measure which spellings of a metric filter Snowflake and Databricks accept (D4).

D4 (REQUIREMENTS.md) says: verify live first; compile a metric filter to HAVING if both
warehouses accept it, else reject it at validation. This script is that measurement. For
each warehouse it builds the same temp ``sales_data`` table and ``sales_view`` the
integration fixtures build (``tests/integration/conftest.py``), runs every candidate
spelling over the real ADBC pool, records whether the warehouse accepted it and what rows
came back, drops the temp schema, and writes ``53-D4-METRIC-FILTER.md`` next to itself.

Every candidate filters on ``revenue > 1500``. The rows say which semantics were applied,
not just whether the SQL parsed:

- post-aggregation (HAVING semantics): ``[("CA", 2800)]``
- row-level, before aggregation: ``[("CA", 2000)]`` (only the 2000 row survives)

Errors are recorded rather than raised, which is why this is a script and not a cassette
test: pytest-adbc-replay records results, not refusals.

Run from the repo root, with the same credentials the cassette recording uses::

    uv run python .planning/phases/53-portable-result-column-names/probe_metric_filter_live.py

Pass ``snowflake`` or ``databricks`` to probe one warehouse only.
"""

from __future__ import annotations

import sys
import traceback
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests" / "integration"))

from conftest import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    _databricks_native_kwargs,  # pyright: ignore[reportUnknownVariableType]
    _snowflake_native_kwargs,  # pyright: ignore[reportUnknownVariableType]
)

from semolina.config import create_engine, warehouse_config  # noqa: E402

OUT = Path(__file__).with_name("53-D4-METRIC-FILTER.md")

POST_AGGREGATION = [("CA", 2800)]
ROW_LEVEL = [("CA", 2000)]

# (shape id, what it tests, SQL). {m}/{c}: metric/cost expression, {a}: revenue alias,
# {country}: the dimension column, {country_a}: its alias, {view}: the view.
SHAPES: list[tuple[str, str, str]] = [
    (
        "where_bare",
        "what Semolina sends today: the bare metric name in WHERE",
        "SELECT {m} AS {a}, {country} AS {country_a} FROM {view}"
        " WHERE {bare} > 1500 GROUP BY ALL ORDER BY {country_a}",
    ),
    (
        "where_wrapped",
        "the wrapped metric in WHERE",
        "SELECT {m} AS {a}, {country} AS {country_a} FROM {view}"
        " WHERE {m} > 1500 GROUP BY ALL ORDER BY {country_a}",
    ),
    (
        "having_wrapped",
        "the wrapped metric in HAVING, metric selected",
        "SELECT {m} AS {a}, {country} AS {country_a} FROM {view}"
        " GROUP BY ALL HAVING {m} > 1500 ORDER BY {country_a}",
    ),
    (
        "having_alias",
        "the select alias in HAVING, metric selected",
        "SELECT {m} AS {a}, {country} AS {country_a} FROM {view}"
        " GROUP BY ALL HAVING {a} > 1500 ORDER BY {country_a}",
    ),
    (
        "having_wrapped_unselected",
        "the wrapped metric in HAVING, metric not selected",
        "SELECT {c} AS {c_a}, {country} AS {country_a} FROM {view}"
        " GROUP BY ALL HAVING {m} > 1500 ORDER BY {country_a}",
    ),
    (
        "having_wrapped_no_dimensions",
        "HAVING on a metric-only query, which has no GROUP BY",
        "SELECT {m} AS {a} FROM {view} HAVING {m} > 1000",
    ),
    (
        "outer_where_alias",
        "the aggregate query as a subquery, filtered outside on the alias",
        "SELECT * FROM (SELECT {m} AS {a}, {country} AS {country_a} FROM {view}"
        " GROUP BY ALL) WHERE {a} > 1500 ORDER BY {country_a}",
    ),
]

SPELLINGS: dict[str, dict[str, str]] = {
    "snowflake": {
        "m": 'AGG("REVENUE")',
        "bare": '"REVENUE"',
        "c": 'AGG("COST")',
        "a": '"revenue"',
        "c_a": '"cost"',
        "country": '"COUNTRY"',
        "country_a": '"country"',
        "view": '"SALES_VIEW"',
    },
    "databricks": {
        "m": "MEASURE(`revenue`)",
        "bare": "`revenue`",
        "c": "MEASURE(`cost`)",
        "a": "`revenue`",
        "c_a": "`cost`",
        "country": "`country`",
        "country_a": "`country`",
        "view": "`sales_view`",
    },
}


def _norm(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _snowflake_setup() -> tuple[Any, Any]:
    import snowflake.connector  # type: ignore[import-not-found]

    base = warehouse_config("snowflake")
    if not base.database:
        sys.exit("Set `database` in [connections.snowflake]: the driver ignores a bare schema.")
    schema = f"TEST_D4_{uuid.uuid4().hex[:8].upper()}"
    native = _snowflake_native_kwargs(base)
    with snowflake.connector.connect(**native) as conn, conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(f"CREATE SCHEMA {schema}")
        cur.execute(f"USE SCHEMA {schema}")
        cur.execute(
            "CREATE TABLE sales_data (revenue NUMBER, cost NUMBER, country VARCHAR, region VARCHAR)"
        )
        cur.execute(
            "INSERT INTO sales_data VALUES (1000, 100, 'US', 'West'), (2000, 200, 'CA', 'East'),"
            " (500, 50, 'US', 'East'), (1500, 150, 'MX', 'South'), (800, 80, 'CA', 'West')"
        )
        cur.execute(
            "CREATE SEMANTIC VIEW sales_view TABLES (sales_data)"
            " DIMENSIONS (sales_data.country AS country, sales_data.region AS region)"
            " METRICS (sales_data.revenue AS SUM(revenue), sales_data.cost AS SUM(cost))"
        )

    def teardown() -> None:
        with snowflake.connector.connect(**native) as conn, conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")

    return create_engine(base.model_copy(update={"schema_": schema})), teardown


def _databricks_setup() -> tuple[Any, Any]:
    import databricks.sql  # type: ignore[import-not-found]

    base = warehouse_config("databricks")
    catalog = base.catalog
    schema = f"TEST_D4_{uuid.uuid4().hex[:8].upper()}"
    native = _databricks_native_kwargs(base)
    with databricks.sql.connect(**native) as conn, conn.cursor() as cur:  # type: ignore[attr-defined]
        cur.execute(f"CREATE SCHEMA {catalog}.{schema}")
        cur.execute(
            f"CREATE TABLE {catalog}.{schema}.sales_data"
            " (revenue BIGINT, cost BIGINT, country STRING, region STRING)"
        )
        cur.execute(
            f"INSERT INTO {catalog}.{schema}.sales_data VALUES (1000, 100, 'US', 'West'),"
            " (2000, 200, 'CA', 'East'), (500, 50, 'US', 'East'), (1500, 150, 'MX', 'South'),"
            " (800, 80, 'CA', 'West')"
        )
        cur.execute(
            f"CREATE OR REPLACE VIEW {catalog}.{schema}.sales_view"
            " WITH METRICS LANGUAGE YAML AS $$\n"
            "version: 1.1\n"
            f"source: {catalog}.{schema}.sales_data\n"
            "dimensions:\n  - name: country\n    expr: country\n"
            "  - name: region\n    expr: region\n"
            "measures:\n  - name: revenue\n    expr: SUM(revenue)\n"
            "  - name: cost\n    expr: SUM(cost)\n$$"
        )

    def teardown() -> None:
        with databricks.sql.connect(**native) as conn, conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(f"DROP SCHEMA IF EXISTS {catalog}.{schema} CASCADE")

    return create_engine(base.model_copy(update={"schema_": schema})), teardown


def _verdict(rows: list[tuple[Any, ...]], shape: str) -> str:
    if shape == "having_wrapped_no_dimensions":
        return "post-aggregation" if rows == [(5800,)] else "unexpected"
    if shape == "having_wrapped_unselected":
        return "post-aggregation" if rows == [(280, "CA")] else "unexpected"
    if rows == [(r, c) for c, r in POST_AGGREGATION]:
        return "post-aggregation"
    if rows == [(r, c) for c, r in ROW_LEVEL]:
        return "row-level"
    return "unexpected"


def probe(warehouse: str) -> list[dict[str, str]]:
    engine, teardown = (_snowflake_setup if warehouse == "snowflake" else _databricks_setup)()
    results: list[dict[str, str]] = []
    try:
        for shape, what, template in SHAPES:
            sql = template.format(**SPELLINGS[warehouse])
            try:
                with engine.connect() as conn:
                    cur = conn.cursor()
                    try:
                        cur.execute(sql)
                        rows = [tuple(_norm(v) for v in row) for row in cur.fetchall()]
                    finally:
                        cur.close()
                results.append(
                    {
                        "shape": shape,
                        "what": what,
                        "sql": sql,
                        "outcome": f"accepted, {_verdict(rows, shape)}",
                        "detail": repr(rows),
                    }
                )
            except Exception as e:  # noqa: BLE001 - a refusal is the measurement
                # Whole message on one line: Snowflake puts the reason after the
                # "SQL compilation error:" line.
                first = " ".join(str(e).split())[:400]
                results.append(
                    {
                        "shape": shape,
                        "what": what,
                        "sql": sql,
                        "outcome": f"refused ({type(e).__name__})",
                        "detail": first,
                    }
                )
            print(f"{warehouse:10} {shape:30} {results[-1]['outcome']}")
    finally:
        engine.dispose()
        teardown()
    return results


def render(all_results: dict[str, list[dict[str, str]]]) -> str:
    lines = [
        "# D4 live probe: metric filters on Snowflake and Databricks",
        "",
        f"Measured {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `probe_metric_filter_live.py` "
        "(rerun it to refresh; do not edit by hand).",
        "",
        "Every candidate filters on `revenue > 1500` over the integration fixture's data. "
        "Post-aggregation (HAVING) semantics return `CA 2800`; row-level semantics return "
        "`CA 2000`. The unselected-metric shape selects `cost`, so it expects `CA 280`; the "
        "metric-only shape filters `> 1000` and expects the 5800 total.",
        "",
    ]
    for warehouse, results in all_results.items():
        lines += [f"## {warehouse}", "", "| Shape | Tests | Outcome | Rows or error |"]
        lines.append("|---|---|---|---|")
        for r in results:
            detail = r["detail"].replace("|", "\\|")
            lines.append(f"| `{r['shape']}` | {r['what']} | {r['outcome']} | {detail} |")
        lines += ["", "SQL sent:", "", "```sql"]
        lines += [f"-- {r['shape']}\n{r['sql']}" for r in results]
        lines += ["```", ""]
    return "\n".join(lines)


def main() -> None:
    targets = sys.argv[1:] or ["snowflake", "databricks"]
    all_results: dict[str, list[dict[str, str]]] = {}
    for warehouse in targets:
        try:
            all_results[warehouse] = probe(warehouse)
        except Exception:  # noqa: BLE001 - report setup failures and keep the other warehouse
            traceback.print_exc()
            print(f"{warehouse}: setup failed, skipped")
    if all_results:
        OUT.write_text(render(all_results))
        print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
