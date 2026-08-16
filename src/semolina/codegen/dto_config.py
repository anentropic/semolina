"""
Read a project's declared DTO codegen inputs from ``pyproject.toml``.

The third route into DTO codegen, beside a dotted path and an ad-hoc
``--view``/``--metrics``/``--dimensions``. Those two describe *one* generated class per
invocation; this one lets a project write down every DTO it wants, once, and regenerate the
lot with a bare ``semolina codegen-dto``.

``pyproject.toml`` rather than ``.semolina.toml`` on purpose. The two files answer different
questions and have different fates in a repository: ``.semolina.toml`` carries connection
credentials and is the file this project's own ``.gitignore`` excludes, while which DTOs a
codebase generates is part of its build description and belongs in the file that is committed
next to the code it generates. The one thing the section does name is a *backend*, which is
a label, not a credential — the credentials still come from ``.semolina.toml`` and the
environment, unchanged.

The section is validated strictly: an unrecognised key is an error rather than something
silently ignored. A config file is read once and then trusted for a long time, so a
mistyped ``dimension = [...]`` that quietly generated a metrics-only DTO would be found by
whoever eventually noticed a missing column, not by whoever made the typo.

Example:
    .. code-block:: toml

        [tool.semolina.dto]
        backend = "duckdb"
        database = "sales.db"
        output = "myapp/dtos.py"

        [[tool.semolina.dto.entries]]
        query = "myapp.queries.revenue_by_region"

        [[tool.semolina.dto.entries]]
        name = "SalesByMonth"
        view = "analytics.sales"
        metrics = ["revenue", "order_count"]
        dimensions = ["month", "region"]
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_CONFIG_FILE = "pyproject.toml"
"""The file consulted when no ``--config`` was given."""

SECTION = "[tool.semolina.dto]"
"""The section's own name, quoted back at the user in every diagnostic this module raises."""

ENTRIES_SECTION = "[[tool.semolina.dto.entries]]"
"""The array-of-tables holding one declared DTO each."""

_TOP_LEVEL_KEYS = frozenset({"backend", "database", "output", "entries"})
"""Keys allowed directly under :data:`SECTION`."""

_ENTRY_KEYS = frozenset({"name", "query", "view", "metrics", "dimensions"})
"""Keys allowed in a ``[[tool.semolina.dto.entries]]`` table."""


@dataclass(frozen=True)
class DtoEntry:
    """
    One declared DTO: either an importable query, or a view plus the fields to project.

    The two are mutually exclusive and exactly one must be present, which
    :func:`load_dto_config` enforces before this record is built. Keeping both on one
    dataclass rather than splitting into two types is what lets the CLI hold a single
    ordered list and emit the classes in the order the file declares them, whichever route
    each one came by.

    Attributes:
        class_name: The generated class's name, from the entry's ``name`` key. ``None``
            means "derive it" — from the query attribute for a query entry, from the view
            name for a view entry.
        query: A dotted path to a module-level query, or ``None`` for a view entry.
        view: A semantic view name, or ``None`` for a query entry.
        metrics: Metric field names. Always empty for a query entry.
        dimensions: Dimension field names. Always empty for a query entry.
    """

    class_name: str | None
    query: str | None
    view: str | None
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]


@dataclass(frozen=True)
class DtoConfig:
    """
    A project's whole declared DTO codegen input.

    Attributes:
        path: The file the section was read from, carried so every diagnostic downstream can
            name it rather than saying "the config".
        backend: The ``--backend`` value the section declares, or ``None``.
        database: The DuckDB database path, already resolved against the config file's own
            directory, or ``None``.
        output: The destination file, already resolved against the config file's own
            directory, or ``None`` for stdout.
        entries: The declared DTOs, in the order the file lists them. Never empty.
    """

    path: Path
    backend: str | None
    database: str | None
    output: Path | None
    entries: tuple[DtoEntry, ...]


def _as_table(value: object, where: str, config_path: Path) -> dict[str, Any]:
    """
    Narrow a parsed TOML value to a table, or say what it was instead.

    Args:
        value: The parsed value.
        where: The key path, for the message.
        config_path: The file being read.

    Returns:
        The table.

    Raises:
        ValueError: If the value is not a table.
    """
    if not isinstance(value, dict):
        msg = f"{where} in {config_path} must be a table, not a {type(value).__name__}."
        raise ValueError(msg)
    return value


def _check_keys(table: dict[str, Any], allowed: frozenset[str], where: str, path: Path) -> None:
    """
    Refuse a key the section does not define.

    Args:
        table: The parsed table.
        allowed: Every key this table may carry.
        where: The key path, for the message.
        path: The file being read.

    Raises:
        ValueError: If the table carries a key outside ``allowed``. The message lists the
            allowed keys, because the usual cause is a near-miss spelling.
    """
    unknown = sorted(set(table) - allowed)
    if unknown:
        msg = (
            f"{where} in {path} has no key {unknown[0]!r}. "
            f"Allowed keys: {', '.join(sorted(allowed))}."
        )
        raise ValueError(msg)


def _string(table: dict[str, Any], key: str, where: str, path: Path) -> str | None:
    """
    Read an optional string key.

    Args:
        table: The parsed table.
        key: The key to read.
        where: The key path, for the message.
        path: The file being read.

    Returns:
        The string, or ``None`` if the key is absent.

    Raises:
        ValueError: If the key is present but is not a string, or is empty. An empty string
            is refused rather than treated as absent: ``output = ""`` is a mistake, and
            silently writing to stdout instead would be the wrong repair.
    """
    if key not in table:
        return None
    value: object = table[key]
    if not isinstance(value, str):
        msg = f"{where} key {key!r} in {path} must be a string, not a {type(value).__name__}."
        raise ValueError(msg)
    if not value:
        msg = f"{where} key {key!r} in {path} is empty."
        raise ValueError(msg)
    return value


def _string_list(table: dict[str, Any], key: str, where: str, path: Path) -> tuple[str, ...]:
    """
    Read an optional array-of-strings key.

    Args:
        table: The parsed table.
        key: The key to read.
        where: The key path, for the message.
        path: The file being read.

    Returns:
        The strings, or an empty tuple if the key is absent.

    Raises:
        ValueError: If the key is present but is not an array of strings. A bare string is
            called out by name, because ``metrics = "revenue"`` is the mistake TOML makes
            easy and iterating it as characters is the failure it would otherwise become.
    """
    if key not in table:
        return ()
    value: object = table[key]
    if isinstance(value, str):
        msg = (
            f"{where} key {key!r} in {path} must be an array of strings, not a string. "
            f'Write {key} = ["{value}"].'
        )
        raise ValueError(msg)
    if not isinstance(value, list):
        msg = (
            f"{where} key {key!r} in {path} must be an array of strings, "
            f"not a {type(value).__name__}."
        )
        raise ValueError(msg)
    items: list[Any] = value
    for item in items:
        if not isinstance(item, str):
            msg = (
                f"{where} key {key!r} in {path} must contain only strings; "
                f"found a {type(item).__name__}."
            )
            raise ValueError(msg)
    return tuple(str(item) for item in items)


def _entry(table: dict[str, Any], index: int, path: Path) -> DtoEntry:
    """
    Validate one ``[[tool.semolina.dto.entries]]`` table.

    Args:
        table: The parsed entry table.
        index: Its position in the array, for the message.
        path: The file being read.

    Returns:
        The validated entry.

    Raises:
        ValueError: If the entry names neither a query nor a view, names both, or attaches
            ``metrics`` / ``dimensions`` to a query entry. The last is refused rather than
            ignored because it means the writer expected those fields to *do* something: an
            importable query already carries its own projection, and silently generating a
            DTO from a different set of fields than the file appears to ask for is the exact
            failure strict validation is here to prevent.
    """
    where = f"{ENTRIES_SECTION} #{index + 1}"
    _check_keys(table, _ENTRY_KEYS, where, path)

    query = _string(table, "query", where, path)
    view = _string(table, "view", where, path)
    metrics = _string_list(table, "metrics", where, path)
    dimensions = _string_list(table, "dimensions", where, path)

    if query is None and view is None:
        msg = (
            f"{where} in {path} names neither a query nor a view. Give it either "
            'query = "myapp.queries.revenue_by_region" or view = "analytics.sales" with '
            "metrics/dimensions."
        )
        raise ValueError(msg)
    if query is not None and view is not None:
        msg = (
            f"{where} in {path} names both a query and a view. An importable query already "
            "carries its projection, so the two routes are alternatives -- use one entry for "
            "each."
        )
        raise ValueError(msg)
    if query is not None and (metrics or dimensions):
        msg = (
            f"{where} in {path} sets metrics/dimensions alongside query. The DTO is derived "
            "from the query's own projection, so those keys would have no effect. Drop them, "
            "or replace query with view."
        )
        raise ValueError(msg)

    return DtoEntry(
        class_name=_string(table, "name", where, path),
        query=query,
        view=view,
        metrics=metrics,
        dimensions=dimensions,
    )


def load_dto_config(path: Path) -> DtoConfig | None:
    """
    Read the ``[tool.semolina.dto]`` section of a TOML file.

    Relative ``database`` and ``output`` paths are resolved against the **config file's own
    directory**, not the working directory. A committed ``output = "myapp/dtos.py"`` means
    the same file whether it is regenerated from the project root or from a subdirectory,
    which is what makes the declaration reusable rather than a note about where someone
    happened to be standing. The ``:memory:`` DuckDB sentinel is left alone.

    Args:
        path: The TOML file to read.

    Returns:
        The parsed section, or ``None`` when the file does not exist or carries no
        ``[tool.semolina.dto]`` table. The two are collapsed deliberately: both mean "this
        project has declared nothing", and the caller has one thing to say about it.

    Raises:
        ValueError: If the file is not valid TOML, if the section carries an unrecognised or
            wrongly-typed key, or if it declares no entries.

    Example:
        .. code-block:: python

            from pathlib import Path

            from semolina.codegen.dto_config import load_dto_config

            config = load_dto_config(Path("pyproject.toml"))
            [entry.query for entry in config.entries] if config else []
            # ['myapp.queries.revenue_by_region']
    """
    if not path.is_file():
        return None

    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        msg = f"Cannot read {path}: {e}"
        raise ValueError(msg) from e

    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    semolina: object = tool.get("semolina")
    if not isinstance(semolina, dict):
        return None
    semolina_table: dict[str, Any] = semolina
    if "dto" not in semolina_table:
        return None

    section = _as_table(semolina_table["dto"], SECTION, path)
    _check_keys(section, _TOP_LEVEL_KEYS, SECTION, path)

    raw_entries: object = section.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        msg = (
            f"{SECTION} in {path} declares no DTOs. Add at least one "
            "[[tool.semolina.dto.entries]] table naming a query or a view."
        )
        raise ValueError(msg)
    entry_tables: list[Any] = raw_entries

    entries = tuple(
        _entry(_as_table(table, f"{ENTRIES_SECTION} #{i + 1}", path), i, path)
        for i, table in enumerate(entry_tables)
    )

    root = path.parent
    database = _string(section, "database", SECTION, path)
    if database is not None and database != ":memory:":
        database = str((root / database).expanduser())
    output = _string(section, "output", SECTION, path)

    return DtoConfig(
        path=path,
        backend=_string(section, "backend", SECTION, path),
        database=database,
        output=(root / output) if output is not None else None,
        entries=entries,
    )
