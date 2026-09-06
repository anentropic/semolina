"""
The ``[tool.semolina.dto]`` reader, tested on the file rather than through the CLI.

``test_dto_cli.py`` proves the command honours a config; this module proves the *parser*,
which is where the interesting behaviour is. A config file is written once and then trusted
for a long time, so the property under test throughout is that a mistake in it is reported
rather than absorbed: an unknown key, a wrong type, a query entry carrying field lists that
could not do anything. Every one of those has a silent-success shape available to it, and
each test below names the shape it is ruling out.

No engine, no warehouse and no import of the user's code: the parser touches none of them,
which is what lets these cases be a handful of ``tmp_path`` writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from semolina.codegen.dto_config import load_dto_config

if TYPE_CHECKING:
    from pathlib import Path

FULL_CONFIG = """
[project]
name = "myapp"

[tool.semolina.dto]
backend = "duckdb"
database = "warehouse/sales.db"
output = "myapp/dtos.py"

[[tool.semolina.dto.entries]]
query = "myapp.queries.revenue_by_region"

[[tool.semolina.dto.entries]]
name = "SalesByMonth"
view = "analytics.sales"
metrics = ["revenue", "order_count"]
dimensions = ["month", "region"]
"""
"""
A section using every key, including the ``[project]`` table it shares the file with.

The unrelated table is deliberate: the reader looks up ``tool.semolina.dto`` in a real
``pyproject.toml``, so a parser that assumed the file held only its own section would pass a
test built on a file that held only its own section.
"""


def _write(tmp_path: Path, source: str, name: str = "pyproject.toml") -> Path:
    """
    Write a config file and return its path.

    Args:
        tmp_path: pytest's per-test temporary directory.
        source: The TOML source.
        name: The file name.

    Returns:
        The written path.
    """
    path = tmp_path / name
    path.write_text(source)
    return path


class TestASectionThatParses:
    """The shape the how-to documents, read back field by field."""

    def test_both_entry_kinds_are_read_in_file_order(self, tmp_path: Path) -> None:
        """
        A query entry and a view entry coexist, and the order is the file's.

        Order is asserted rather than assumed because it is the emission order of the
        generated classes: the reader returns a tuple and the CLI does not sort it, so a
        file that lists the view entry first must generate that class first.
        """
        config = load_dto_config(_write(tmp_path, FULL_CONFIG))

        assert config is not None
        assert [entry.query for entry in config.entries] == [
            "myapp.queries.revenue_by_region",
            None,
        ]
        assert [entry.view for entry in config.entries] == [None, "analytics.sales"]
        assert config.entries[1].metrics == ("revenue", "order_count")
        assert config.entries[1].dimensions == ("month", "region")
        assert config.entries[1].class_name == "SalesByMonth"
        assert config.entries[0].class_name is None

    def test_relative_paths_resolve_against_the_config_file_not_the_cwd(
        self, tmp_path: Path
    ) -> None:
        """
        ``output = "myapp/dtos.py"`` means the same file wherever the command is run from.

        The load-bearing half is that the parent directory is the *config file's*, which is
        asserted by reading the config from a subdirectory the test never chdirs into. A
        cwd-relative implementation passes a test run from the config's own directory and
        writes to the wrong place the first time someone regenerates from a sibling folder.
        """
        project = tmp_path / "project"
        project.mkdir()
        config = load_dto_config(_write(project, FULL_CONFIG))

        assert config is not None
        assert config.output == project / "myapp" / "dtos.py"
        assert config.database == str(project / "warehouse" / "sales.db")

    def test_the_memory_sentinel_is_not_treated_as_a_path(self, tmp_path: Path) -> None:
        """
        ``database = ":memory:"`` survives unchanged.

        Resolving it against the config directory would produce a path the DuckDB driver
        then tries to open as a file, turning a legal value into a confusing failure.
        """
        source = FULL_CONFIG.replace('database = "warehouse/sales.db"', 'database = ":memory:"')
        config = load_dto_config(_write(tmp_path, source))

        assert config is not None
        assert config.database == ":memory:"

    def test_the_optional_settings_may_all_be_absent(self, tmp_path: Path) -> None:
        """
        A section may declare entries and nothing else, leaving the flags to supply the rest.

        This is the shape a project uses when the backend differs per environment: the file
        says which DTOs exist, the command line says where to probe them.
        """
        config = load_dto_config(
            _write(
                tmp_path,
                """
                [[tool.semolina.dto.entries]]
                query = "myapp.queries.revenue_by_region"
                """,
            )
        )

        assert config is not None
        assert (config.backend, config.database, config.output) == (None, None, None)
        assert len(config.entries) == 1


class TestNothingDeclared:
    """
    The two ways a project can have no config, which answer the same way on purpose.

    Both mean "this project has declared nothing", and the caller has one thing to say about
    it. Distinguishing them here would push a choice onto the CLI that it has no better
    answer for than the one message naming all three routes.
    """

    def test_a_file_that_does_not_exist_is_not_an_error(self, tmp_path: Path) -> None:
        """A project with no ``pyproject.toml`` has simply not opted in."""
        assert load_dto_config(tmp_path / "pyproject.toml") is None

    def test_a_file_with_no_section_is_not_an_error(self, tmp_path: Path) -> None:
        """Neither has a project whose ``pyproject.toml`` says nothing about Semolina."""
        assert load_dto_config(_write(tmp_path, '[project]\nname = "myapp"\n')) is None

    def test_a_tool_table_without_a_dto_key_is_not_an_error(self, tmp_path: Path) -> None:
        """
        ``[tool.semolina]`` carrying other keys one day must not read as an empty section.

        The reader looks up ``dto`` rather than assuming a ``[tool.semolina]`` table is one,
        so a future sibling section cannot make this command claim a project declared no
        DTOs when it declared nothing at all.
        """
        assert load_dto_config(_write(tmp_path, "[tool.semolina]\nsomething = 1\n")) is None


class TestAMistakeIsReportedRatherThanAbsorbed:
    """
    Every wrong key, wrong type and impossible combination, each named by what it rules out.

    The section is validated strictly because the failure mode of leniency here is delayed
    and quiet: a mistyped key that is ignored generates a DTO that is subtly not the one the
    file asks for, and the person who finds it is not the person who typed it.
    """

    def test_an_unknown_top_level_key_names_the_key_and_the_allowed_ones(
        self, tmp_path: Path
    ) -> None:
        """
        ``outputs = ...`` is a typo, not a new feature, and it must not be dropped.

        Silently ignoring it writes the generated module to stdout while the file appears to
        say otherwise, which is the whole class of failure this validation exists for. The
        allowed keys are listed in the message because the cause is nearly always a
        near-miss spelling.
        """
        source = FULL_CONFIG.replace("output =", "outputs =")

        with pytest.raises(ValueError, match=r"has no key 'outputs'") as excinfo:
            load_dto_config(_write(tmp_path, source))

        assert "output" in str(excinfo.value)

    def test_an_unknown_entry_key_names_the_entry_by_position(self, tmp_path: Path) -> None:
        """
        A bad key in the *second* entry says so, because a file can hold many.

        Position rather than nothing: the entries are anonymous when they carry no ``name``,
        so "one of your entries is wrong" would leave the reader diffing them by hand.
        """
        source = FULL_CONFIG.replace("dimensions = [", "dimension = [")

        with pytest.raises(ValueError, match=r"#2 in .* has no key 'dimension'"):
            load_dto_config(_write(tmp_path, source))

    def test_an_entry_naming_neither_a_query_nor_a_view_is_refused(self, tmp_path: Path) -> None:
        """An entry with only a ``name`` describes no DTO at all."""
        with pytest.raises(ValueError, match=r"names neither a query nor a view"):
            load_dto_config(
                _write(tmp_path, '[[tool.semolina.dto.entries]]\nname = "Orphan"\n'),
            )

    def test_an_entry_naming_both_a_query_and_a_view_is_refused(self, tmp_path: Path) -> None:
        """
        The two routes are alternatives, so an entry claiming both has no defined meaning.

        Picking one and ignoring the other is available and wrong: whichever this chose, half
        the files that hit it would generate a DTO from a source their author did not intend.
        """
        with pytest.raises(ValueError, match=r"names both a query and a view"):
            load_dto_config(
                _write(
                    tmp_path,
                    "[[tool.semolina.dto.entries]]\n"
                    'query = "myapp.queries.revenue"\n'
                    'view = "analytics.sales"\n',
                )
            )

    def test_field_lists_on_a_query_entry_are_refused_rather_than_ignored(
        self, tmp_path: Path
    ) -> None:
        """
        ``metrics`` beside ``query`` would do nothing, and doing nothing quietly is worse.

        An importable query carries its own projection, so these keys cannot narrow it. The
        author who wrote them expected a projection they will not get, and the generated
        class is the only place they would ever find out.
        """
        with pytest.raises(ValueError, match=r"sets metrics/dimensions alongside query"):
            load_dto_config(
                _write(
                    tmp_path,
                    "[[tool.semolina.dto.entries]]\n"
                    'query = "myapp.queries.revenue"\n'
                    'metrics = ["revenue"]\n',
                )
            )

    def test_a_section_with_no_entries_is_refused(self, tmp_path: Path) -> None:
        """
        An empty section is a half-written config, not an instruction to generate nothing.

        Reading it as "generate nothing" exits ``0`` having done nothing, which in CI is
        indistinguishable from success.
        """
        with pytest.raises(ValueError, match=r"declares no DTOs"):
            load_dto_config(_write(tmp_path, '[tool.semolina.dto]\nbackend = "duckdb"\n'))

    def test_a_string_where_an_array_belongs_says_how_to_write_it(self, tmp_path: Path) -> None:
        """
        ``metrics = "revenue"`` is the mistake TOML makes easy, and iterating it is the bug.

        A string is iterable, so an unchecked implementation projects seven single-character
        fields and fails much later with a message about a column named ``r``. The error
        quotes the array form back rather than only refusing.
        """
        with pytest.raises(ValueError, match=r"must be an array of strings, not a string"):
            load_dto_config(
                _write(
                    tmp_path,
                    "[[tool.semolina.dto.entries]]\n"
                    'view = "analytics.sales"\n'
                    'metrics = "revenue"\n',
                )
            )

    def test_a_non_string_inside_an_array_is_refused(self, tmp_path: Path) -> None:
        """A number among the field names cannot be normalized or quoted into a field."""
        with pytest.raises(ValueError, match=r"must contain only strings"):
            load_dto_config(
                _write(
                    tmp_path,
                    "[[tool.semolina.dto.entries]]\n"
                    'view = "analytics.sales"\n'
                    'metrics = ["revenue", 3]\n',
                )
            )

    def test_a_non_string_setting_is_refused_by_the_type_it_actually_is(
        self, tmp_path: Path
    ) -> None:
        """``backend = true`` names the type found, the way the query resolver does."""
        with pytest.raises(ValueError, match=r"must be a string, not a bool"):
            load_dto_config(
                _write(
                    tmp_path,
                    "[tool.semolina.dto]\nbackend = true\n"
                    "[[tool.semolina.dto.entries]]\n"
                    'query = "myapp.queries.revenue"\n',
                )
            )

    def test_an_empty_setting_is_refused_rather_than_read_as_absent(self, tmp_path: Path) -> None:
        """
        ``output = ""`` is a mistake, and falling back to stdout would be the wrong repair.

        Treating an empty string as "unset" hides the typo behind behaviour that looks
        deliberate, and the generated module lands in a terminal instead of in the file the
        config names.
        """
        with pytest.raises(ValueError, match=r"key 'output' in .* is empty"):
            load_dto_config(
                _write(
                    tmp_path,
                    '[tool.semolina.dto]\noutput = ""\n'
                    "[[tool.semolina.dto.entries]]\n"
                    'query = "myapp.queries.revenue"\n',
                )
            )

    def test_malformed_toml_names_the_file(self, tmp_path: Path) -> None:
        """A syntax error reports as this reader's own ValueError, naming the path."""
        with pytest.raises(ValueError, match=r"Cannot read .*pyproject.toml"):
            load_dto_config(_write(tmp_path, "[tool.semolina.dto\n"))

    def test_a_section_that_is_not_a_table_is_refused(self, tmp_path: Path) -> None:
        """``dto = "yes"`` is not a section, and the message says what it found instead."""
        with pytest.raises(ValueError, match=r"must be a table, not a str"):
            load_dto_config(_write(tmp_path, '[tool.semolina]\ndto = "yes"\n'))
