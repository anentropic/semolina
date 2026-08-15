"""
The DTO codegen CLI surface, driven end to end through ``CliRunner``.

``test_dto_codegen_e2e.py`` proves the pipeline; this module proves the *published command*
over it — the positional dotted path, the option set, and every documented exit code. The
distinction matters because a CLI is a contract with scripts: the pipeline raising a
``ValueError`` and the command exiting ``6`` are two different claims, and only the second
one is what a CI job reads.

The probe backend is a file-backed DuckDB carrying the type-fidelity view, because the CLI
builds its *own* engine from ``--backend`` / ``--database`` rather than being handed one. The
in-memory ``probe_engine`` the other modules use is unreachable from a subprocess-shaped
surface, so the fixture below writes the same DDL to a real file.

The dotted paths are real import paths into ``tests/unit/codegen/fixtures/dto_queries.py``.
Nothing here monkeypatches resolution: ``tests/unit/codegen/__init__.py`` makes ``tests/unit``
an import root under pytest, so ``codegen.fixtures.dto_queries.value_by_region`` is a path the
resolver imports for real.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from semolina.cli import app
from semolina.cli.codegen import EXIT_INVALID_BACKEND
from semolina.cli.dto_codegen import EXIT_PROBE_FAILED

if TYPE_CHECKING:
    from pathlib import Path

    # Typer's own Result, not click's. Typer subclasses it to split the two streams back
    # apart -- `stdout` and `stderr` are separate attributes -- which is the whole reason
    # this module can assert that a diagnostic never reached the source stream.
    from syrupy.assertion import SnapshotAssertion
    from typer.testing import Result

    from semolina.query import _Query

runner = CliRunner()

VALUE_BY_REGION = "codegen.fixtures.dto_queries.value_by_region"
"""Dotted path to the headline fixture query, resolved by the CLI for real."""

COUNTS_BY_REGION = "codegen.fixtures.dto_queries.counts_by_region"
"""Dotted path to the second fixture query, for the several-paths-in-one-invocation case."""

NOT_A_QUERY = "codegen.fixtures.dto_queries.not_a_query"
"""Dotted path to a module-level attribute that resolves to a ``str``."""


@pytest.fixture(scope="session")
def type_fidelity_file_backed_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Write the type-fidelity probe fixture to an on-disk DuckDB the CLI can open.

    The DDL is imported from ``type_fidelity_probe`` rather than pasted: the queries in
    ``codegen.fixtures.dto_queries`` are built on that module's ``TypeFidelityView``, so a
    second copy of the view definition drifting from the model is the one failure this
    fixture could introduce on its own.

    Session-scoped and built through ``tmp_path_factory`` for the same reasons
    ``duckdb_file_backed_db`` is: the community-extension install is paid once per xdist
    worker, and each worker gets its own directory so ``-n auto`` cannot race.

    Args:
        tmp_path_factory: pytest's per-worker temporary directory factory.

    Returns:
        Path to a ``.db`` carrying ``type_fidelity_view`` and its seed rows.
    """
    import duckdb  # pyright: ignore[reportMissingImports]
    from type_fidelity_probe import PROBE_SEED_DML, PROBE_TABLE_DDL, PROBE_VIEW_DDL

    db_path = tmp_path_factory.mktemp("dto_cli_fixture") / "type_fidelity.db"
    conn = duckdb.connect(database=str(db_path))
    try:
        conn.execute("INSTALL semantic_views FROM community")
        conn.execute("LOAD semantic_views")
        conn.execute(PROBE_TABLE_DDL)
        conn.execute(PROBE_SEED_DML)
        conn.execute(PROBE_VIEW_DDL)
    finally:
        conn.close()
    return db_path


def _invoke(database: Path, *args: str) -> Result:
    """
    Run ``semolina codegen-dto`` against the file-backed probe database.

    Args:
        database: The ``--database`` path.
        *args: Everything before the backend options — dotted paths and any ``--name``.

    Returns:
        The ``CliRunner`` result. ``stdout`` and ``stderr`` are separate streams on click
        8.3, which is what makes the redirect claim assertable rather than assumed.
    """
    return runner.invoke(
        app,
        ["codegen-dto", *args, "--backend", "duckdb", "--database", str(database)],
    )


def _diagnostics(result: Result) -> str:
    """
    Read stderr back as one unwrapped line.

    Rich hard-wraps to the console width, so a phrase this repo's error messages state as a
    sentence arrives with a newline somewhere inside it — and where, exactly, depends on how
    long the interpolated dotted path was. Collapsing the whitespace lets a test assert what
    the message *says* rather than how wide the terminal was when it said it.

    Args:
        result: The ``CliRunner`` result.

    Returns:
        Stderr with every run of whitespace collapsed to a single space.
    """
    return " ".join(result.stderr.split())


def _class_defs(source: str) -> list[ast.ClassDef]:
    """
    Parse generated source and return its top-level class definitions.

    Args:
        source: The captured stdout.

    Returns:
        Every module-level ``ClassDef``, in emission order.
    """
    return [node for node in ast.parse(source).body if isinstance(node, ast.ClassDef)]


class TestTheSuccessPath:
    """A dotted path in, a committable Pydantic module out."""

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_dotted_path_generates_a_dto_on_stdout(
        self, type_fidelity_file_backed_db: Path, snapshot: SnapshotAssertion
    ) -> None:
        """
        The whole emitted file is pinned in one snapshot a reviewer can read.

        A snapshot rather than a handful of substring assertions because the artifact under
        test *is* a file: its provenance header, its import block, its alias lines and its
        annotations are one object, and a reviewer approving a change to any of them should
        see the others in the same diff. The individual properties already have targeted
        tests in ``test_dto_codegen_e2e.py``; what only the snapshot catches is the file
        quietly gaining or losing a line.
        """
        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION)

        assert result.exit_code == 0, result.output
        assert result.stdout == snapshot

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_stdout_alone_parses_as_python(self, type_fidelity_file_backed_db: Path) -> None:
        """
        Redirecting stdout to a file yields something importable.

        Asserted with ``ast.parse`` rather than by looking for a class name: the property
        the redirect depends on is that *nothing else* landed in the stream, and a substring
        check passes just as happily with a diagnostic line sitting above the imports.

        The pairing assertion matters too. A command that wrote nothing to stdout would also
        parse, so the class has to be there as well.
        """
        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION)

        assert result.exit_code == 0, result.output
        assert [node.name for node in _class_defs(result.stdout)] == ["ValueByRegion"]

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_name_flag_replaces_the_derived_class_name(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """
        ``--name`` overrides the PascalCase form of the query attribute (D-05).

        Both halves are asserted: the override appears and the derived name does not. A
        one-sided check would pass against an implementation that emitted both.
        """
        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--name", "RegionTotals")

        assert result.exit_code == 0, result.output
        assert [node.name for node in _class_defs(result.stdout)] == ["RegionTotals"]

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_several_paths_emit_several_classes_over_one_import_block(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """
        Two queries in one invocation render into one module, not two (O-03).

        The import block is asserted to be shared rather than merely present: two
        concatenated renders would also yield two classes, and would also parse. What
        separates the two shapes is that ``import pydantic`` appears exactly once and that
        every import precedes every class.
        """
        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, COUNTS_BY_REGION)

        assert result.exit_code == 0, result.output
        module = ast.parse(result.stdout)
        classes = [node for node in module.body if isinstance(node, ast.ClassDef)]
        imports = [node for node in module.body if isinstance(node, ast.Import | ast.ImportFrom)]

        assert [node.name for node in classes] == ["ValueByRegion", "CountsByRegion"]
        assert result.stdout.count("import pydantic") == 1, result.stdout
        assert max(module.body.index(i) for i in imports) < min(
            module.body.index(c) for c in classes
        )

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_unformatted_output_note_goes_to_stderr(
        self, type_fidelity_file_backed_db: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The ruff-not-installed note never lands in the source stream.

        ``ruff`` is present in this repo's dev environment, so the note is unreachable
        without forcing it — which means the stdout/stderr split would otherwise be tested
        only on the path that emits no diagnostic at all, and the one diagnostic a
        *successful* run can emit would go unchecked. Forcing it is what turns "diagnostics
        go to stderr" into a claim about the success path too.

        ``ruff_available`` is patched where it is defined rather than where it is used,
        because the command imports it lazily inside its own body.
        """
        from semolina.codegen import python_renderer

        monkeypatch.setattr(python_renderer, "ruff_available", lambda: False)

        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION)

        assert result.exit_code == 0, result.output
        assert "ruff is not installed" in _diagnostics(result), result.stderr
        assert "ruff" not in result.stdout, result.stdout
        assert [node.name for node in _class_defs(result.stdout)] == ["ValueByRegion"]


class TestAPathThatDoesNotResolve:
    """
    Every unresolvable dotted path is exit 2, with the reason on stderr.

    2 rather than 1 because it is the caller's to fix, and because it is the code
    ``semolina codegen`` already uses for a rejected option value — a script handling one
    command's bad input should not need a second branch for the other's.
    """

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_module_that_does_not_exist_names_the_path(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """The message names the module that could not be imported, not just 'failed'."""
        result = _invoke(type_fidelity_file_backed_db, "no_such_module_here.some_query")

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "no_such_module_here" in _diagnostics(result), result.stderr
        assert result.stdout == "", result.stdout

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_an_attribute_that_is_not_a_query_names_the_type_found(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """
        Resolving a ``str`` reports ``str``, because the type is the actionable part.

        The common mistake is pointing at the model class or at the query *builder method*
        rather than at a built query, and "not a query" on its own does not distinguish
        those from each other or from a typo.
        """
        result = _invoke(type_fidelity_file_backed_db, NOT_A_QUERY)

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "resolved to a str, not a query" in _diagnostics(result), result.stderr
        assert result.stdout == "", result.stdout

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_name_with_several_paths_is_refused_before_anything_is_imported(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """
        ``--name`` renames one class, so more than one path is a flag-pairing error.

        The path given is deliberately unimportable. The pairing is validated before the
        modules are resolved, so the message must be about ``--name`` — if it named the
        module instead, the command would have executed a user's code to reject an argument
        it could already reject.
        """
        result = _invoke(
            type_fidelity_file_backed_db,
            "no_such_module_here.a",
            "no_such_module_here.b",
            "--name",
            "Whatever",
        )

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "--name" in _diagnostics(result), result.stderr
        assert "no_such_module_here" not in _diagnostics(result), result.stderr


class TestAFailureNeverBecomesADto:
    """
    The two boundaries plan 50-05 pinned, mapped onto exit 6.

    They fail through different arms of the command — a driver exception out of the probe
    and a ``ValueError`` out of the alias binding — and both must produce a diagnostic and
    no file. DTO codegen has no metadata route to degrade to, so a generated file is the
    wrong answer to either.
    """

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_probe_that_fails_on_both_routes_exits_6(
        self, type_fidelity_file_backed_db: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        ``ExecuteSchema`` refused *and* the zero-row wrapper rejected is a hard failure.

        Both routes are removed, in the shapes ``test_dto_codegen_e2e.py`` established: the
        refusal is a ``NotSupportedError`` (which ``probe_schema`` catches, sending it down
        the fallback) and the fallback is poisoned with a ``ProgrammingError`` matched on the
        ``WHERE 1=0`` wrapper, so only the zero-row statement fails and the connection stays
        real. This is the realistic shape of the unmeasured Databricks risk — a planner that
        rejects the wrapper — reaching a user through the published command.
        """
        import adbc_driver_manager  # pyright: ignore[reportMissingImports]
        import adbc_driver_manager.dbapi  # pyright: ignore[reportMissingImports]

        cursor_cls: Any = adbc_driver_manager.dbapi.Cursor
        real_execute: Any = cursor_cls.execute

        def refuse(self: Any, *args: Any, **kwargs: Any) -> Any:
            raise adbc_driver_manager.NotSupportedError("ExecuteSchema not implemented")

        def execute(self: Any, operation: Any, *args: Any, **kwargs: Any) -> Any:
            if "WHERE 1=0" in str(operation):
                raise adbc_driver_manager.ProgrammingError(
                    "zero-row wrapper rejected by the planner",
                    status_code=adbc_driver_manager.AdbcStatusCode.INVALID_ARGUMENT,
                )
            return real_execute(self, operation, *args, **kwargs)

        monkeypatch.setattr(cursor_cls, "adbc_execute_schema", refuse, raising=True)
        monkeypatch.setattr(cursor_cls, "execute", execute)

        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION)

        assert result.exit_code == EXIT_PROBE_FAILED, result.output
        assert "rejected by the planner" in _diagnostics(result), result.stderr
        assert result.stdout == "", result.stdout

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_field_that_binds_to_no_result_column_exits_6(
        self, type_fidelity_file_backed_db: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        An unbindable alias stops the command rather than emitting a partial class.

        Driven by handing the renderer a probed schema whose columns do not carry the
        projection — the same synthetic-schema shape
        ``TestAnUnbindableAliasIsFatalToo`` uses — because the live DuckDB probe cannot be
        made to answer with a wrong column list without breaking the driver instead. The
        renderer's own binding code still runs and still raises; what is under test here is
        that the CLI turns that into 6 and no file, and the message survives to stderr.
        """
        import pyarrow

        from semolina.codegen import dto_renderer
        from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA

        def mislabelled_probe(
            engine: Any, query: _Query, *, class_name: str, dotted_path: str
        ) -> dto_renderer.ProbedQuery:
            return dto_renderer.ProbedQuery(
                class_name=class_name,
                dotted_path=dotted_path,
                query=query,
                dialect=engine.dialect,
                schema=pyarrow.schema([pyarrow.field("locale", pyarrow.string())]),
                route=ROUTE_EXECUTE_SCHEMA,
            )

        monkeypatch.setattr(dto_renderer, "probe_query", mislabelled_probe)

        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION)

        assert result.exit_code == EXIT_PROBE_FAILED, result.output
        assert "matches no result column" in _diagnostics(result), result.stderr
        assert "'locale'" in _diagnostics(result), result.stderr
        assert result.stdout == "", result.stdout
