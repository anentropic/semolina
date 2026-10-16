"""
Snowflake and Databricks report introspection failures through one shared translation.

The two engines' ``introspect()`` used to carry identical copies of the ADBC-error mapping,
differing only in the backend name, so a change to one could silently miss the other. These
tests pin the mapping once, for both backends, against the single helper they now share.
DuckDB matches on message text instead and keeps its own translator.
"""

from __future__ import annotations

from typing import Any

import adbc_driver_manager
import pytest

from semolina.exceptions import (
    SemolinaConnectionError,
    SemolinaIntrospectionError,
    SemolinaViewNotFoundError,
)


def _adbc(cls: type[adbc_driver_manager.Error]) -> adbc_driver_manager.Error:
    """Build an ADBC error of ``cls`` the way the driver manager would."""
    if cls is adbc_driver_manager.NotSupportedError:
        # The one ADBC error defined in Python, which takes the message alone.
        build: Any = cls
        return build("driver said no")
    return cls("driver said no", status_code=adbc_driver_manager.AdbcStatusCode.INTERNAL)


@pytest.mark.parametrize("backend", ["Snowflake", "Databricks"])
@pytest.mark.parametrize(
    ("raised", "expected", "prefix"),
    [
        (adbc_driver_manager.ProgrammingError, SemolinaViewNotFoundError, "view not found"),
        (adbc_driver_manager.OperationalError, SemolinaConnectionError, "introspection failed"),
        (adbc_driver_manager.InterfaceError, SemolinaConnectionError, "introspection failed"),
        (adbc_driver_manager.InternalError, SemolinaIntrospectionError, "introspection failed"),
        (adbc_driver_manager.DataError, SemolinaIntrospectionError, "introspection failed"),
        (
            adbc_driver_manager.NotSupportedError,
            SemolinaIntrospectionError,
            "introspection failed",
        ),
    ],
)
def test_each_adbc_error_becomes_the_semolina_error_it_means(
    backend: str,
    raised: type[adbc_driver_manager.Error],
    expected: type[Exception],
    prefix: str,
) -> None:
    """Each ADBC error class maps to one Semolina error, named for the backend, cause kept."""
    from semolina.engines.base import _translate_introspection_errors

    error = _adbc(raised)
    with pytest.raises(expected) as caught, _translate_introspection_errors(backend):
        raise error

    assert str(caught.value).startswith(f"{backend} {prefix}")
    assert "driver said no" in str(caught.value)
    assert caught.value.__cause__ is error


def test_anything_but_an_adbc_error_passes_through() -> None:
    """A non-driver exception is not the translation's to rename."""
    from semolina.engines.base import _translate_introspection_errors

    with pytest.raises(KeyError), _translate_introspection_errors("Snowflake"):
        raise KeyError("x")


@pytest.mark.parametrize("module", ["snowflake", "databricks"])
def test_both_warehouse_engines_use_the_shared_translation(module: str) -> None:
    """Neither engine module keeps a private copy of the mapping."""
    import importlib

    engine_module = importlib.import_module(f"semolina.engines.{module}")
    assert not hasattr(engine_module, f"_translate_{module}_errors")
