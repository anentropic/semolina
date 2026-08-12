"""
Shared fixtures for the codegen test package.

Holds the data-fetch guard both ``test_annotation_check.py`` and ``test_cli.py`` use to make
TYPE-07's "without executing a query for rows" runnable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

_METADATA_STATEMENTS = ("DESCRIBE", "SHOW")
"""
Statement prefixes whose rows are catalogue metadata, not view data.

``engine.introspect()`` reads its field list from ``DESCRIBE SEMANTIC VIEW`` /
``DESCRIBE SELECT`` (DuckDB), ``SHOW COLUMNS`` (Snowflake) and ``DESCRIBE TABLE EXTENDED``
(Databricks), and fetching those rows is what introspection *is* — the generation path has
always done it. TYPE-07's guarantee is about the view's **data**, so the guard has to draw
the line here rather than ban ``fetchall`` outright.
"""


@pytest.fixture
def data_fetch_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Make any fetch from a non-metadata statement raise.

    Wraps ``adbc_driver_manager.dbapi.Cursor``: ``execute`` records the statement it ran, and
    the four fetch methods refuse when that statement is not catalogue introspection. A
    ``--check`` run under this guard therefore proves it never materialised a row of the
    view's data, rather than asserting it in prose.

    Args:
        monkeypatch: pytest's patching fixture; the guard is undone at test teardown.
    """
    import adbc_driver_manager.dbapi  # pyright: ignore[reportMissingImports]

    cursor_cls: Any = adbc_driver_manager.dbapi.Cursor
    real_execute: Any = cursor_cls.execute

    def execute(self: Any, operation: Any, *args: Any, **kwargs: Any) -> Any:
        self._guarded_statement = str(operation)
        return real_execute(self, operation, *args, **kwargs)

    def guarded(real: Any) -> Callable[..., Any]:
        def fetch(self: Any, *args: Any, **kwargs: Any) -> Any:
            statement = str(getattr(self, "_guarded_statement", "")).lstrip()
            if not statement.upper().startswith(_METADATA_STATEMENTS):
                raise AssertionError(f"fetched data rows from: {statement}")
            return real(self, *args, **kwargs)

        return fetch

    monkeypatch.setattr(cursor_cls, "execute", execute)
    for name in ("fetchall", "fetchone", "fetchmany", "fetch_arrow_table"):
        monkeypatch.setattr(cursor_cls, name, guarded(getattr(cursor_cls, name)))
