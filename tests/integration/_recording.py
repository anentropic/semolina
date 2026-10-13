"""
Record-mode helpers for the integration fixtures, importable by tests.

Kept out of ``conftest.py`` so a test can import them by a name no other module shares
(``tests/conftest.py`` would shadow a bare ``import conftest``). Not collected: the
name does not match ``test_*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adbc_poolhouse import SnowflakeConfig


def snowflake_query_config(
    base_config: SnowflakeConfig,
    *,
    schema_name: str,
    session_database: str | None,  # noqa: ARG001 - not yet used: the red half of 53-04
) -> SnowflakeConfig:
    """
    Return the config the recording query pool connects with.

    Args:
        base_config: The ``[connections.snowflake]`` config.
        schema_name: The temp schema the fixture created.
        session_database: ``CURRENT_DATABASE()`` of the native session that created it.

    Returns:
        ``base_config`` pointed at the temp schema.
    """
    return base_config.model_copy(update={"schema_": schema_name})
