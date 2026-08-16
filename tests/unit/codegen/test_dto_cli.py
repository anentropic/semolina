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
from semolina.cli.codegen import EXIT_CONNECTION_ERROR, EXIT_INVALID_BACKEND
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

NON_IDENTIFIER_NAMES = [
    pytest.param(
        "X:\n    pass\n\nimport os\nos.system('echo INJECTED')\n\nclass Bar:\n    pass  #",
        id="statement-injection",
    ),
    pytest.param("X;__import__('os')", id="no-whitespace"),
    pytest.param("class", id="keyword"),
    pytest.param("", id="empty"),
]
"""
``--name`` values that cannot be written into ``class <name>(pydantic.BaseModel):``.

The first is the Phase 50 review's proof of concept verbatim — a value that closes the class
statement, adds a top-level ``import os`` and an ``os.system(...)`` call, and reopens a class
whose trailing ``#`` swallows the rest of the template's line. Quoted rather than paraphrased
because a friendlier payload would keep passing against a fix that merely rejected
whitespace; ``test_dto_renderer.py`` carries the parse-level proof that it is executable code
and not a crash, along with the same four shapes checked at the library boundary.

The other three pin the rest of the rule: ``no-whitespace`` is the same threat carrying no
space, ``keyword`` is the case ``str.isidentifier`` gets wrong on its own (it answers
``True`` for ``'class'``), and ``empty`` is what the derived path produces for a dotted path
with no attribute part.
"""


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


class TestAHostileNameNeverReachesTheGeneratedFile:
    """
    Threat T-50-01 at the one sink no escaper can cover: the generated class's own name.

    Every other value this command writes into the file goes through ``_python_str_literal``
    or ``_docstring_body`` first, because a warehouse-supplied string that closes its own
    literal is module-level code execution in a file users import. A class name is not a
    string literal — it is a bare token — so there is nothing to quote it with, and refusing
    it is what stands in for escaping it. ``--name`` is caller input that reaches that token
    unchanged, which makes this the cheaper attack of the two: no warehouse access required,
    just a wrapper or CI job that builds the flag from something untrusted.

    Refused at the same "cheapest and least consequential first" point the ``--name`` pairing
    is, so nothing is imported and no connection is opened to reject an argument.
    """

    @pytest.mark.parametrize("hostile_name", NON_IDENTIFIER_NAMES)
    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_name_that_is_not_an_identifier_exits_2_and_writes_no_source(
        self, type_fidelity_file_backed_db: Path, hostile_name: str
    ) -> None:
        """
        Exit 2, the reason on stderr, and — the load-bearing half — an empty stdout.

        The exit code alone would be satisfied by a command that printed the injected module
        and then failed. What the documented workflow depends on is that ``> myapp/dtos.py``
        captures nothing at all when the name was refused.
        """
        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--name", hostile_name)

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert result.stdout == "", result.stdout
        assert "--name" in _diagnostics(result), result.stderr


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
            engine: Any, query: _Query, *, class_name: str, origin: str
        ) -> dto_renderer.ProbedQuery:
            return dto_renderer.ProbedQuery(
                class_name=class_name,
                origin=origin,
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


class TestADriverThatCannotConnect:
    """
    Exit 4, the code the epilog documents as "Connection or authentication failure".

    UAT test 7 asked whether the exit-code table lists every code the command can return,
    on the premise that 3 and 4 were unreachable because they come from
    ``Engine.introspect``, which DTO codegen never calls. Measured 2026-08-16, the premise
    was wrong in a worse direction than it assumed: a driver that cannot open the database
    escaped as an ``adbc_driver_manager.InternalError`` traceback with exit 1 and an empty
    stderr, because ``_resolve_backend`` builds the engine — and adbc-poolhouse opens a
    connection doing it — outside every handler on the path. Not 6, and not 4: a raw
    traceback out of the one module in this CLI that catches by name everywhere else.
    """

    def test_a_database_that_cannot_be_opened_exits_4(self, tmp_path: Path) -> None:
        """
        A driver-level connection failure is a named exit code, not a traceback.

        The failure is real rather than mocked: a ``--database`` path inside a directory
        that does not exist, which the DuckDB driver refuses at ``AdbcDatabase.__init__``,
        before any Semolina code runs. That is the shape a user hits with a typo in a path
        or an unreachable warehouse host.
        """
        missing = tmp_path / "no-such-directory" / "analytics.db"
        result = runner.invoke(
            app,
            [
                "codegen-dto",
                VALUE_BY_REGION,
                "--backend",
                "duckdb",
                "--database",
                str(missing),
            ],
        )

        assert result.exit_code == EXIT_CONNECTION_ERROR, result.output
        assert result.exception is None or isinstance(result.exception, SystemExit), (
            f"a raw {type(result.exception).__name__} escaped the command"
        )
        assert "could not connect" in _diagnostics(result).lower(), result.stderr
        assert result.stdout == "", result.stdout


class TestTheSiblingCommandAgreesOnConnectionFailure:
    """
    ``semolina codegen`` shares ``_resolve_backend`` and must share the exit code with it.

    The module docstring of :mod:`semolina.cli.dto_codegen` claims the two commands share
    "the diagnostics idiom and the exit-code vocabulary". They did not: ``codegen`` had the
    identical unguarded ``_resolve_backend`` call and escaped the same way, so ``4`` was
    documented and unreachable in *both* epilogs. Fixing one alone would have made that
    claim false in a new direction.
    """

    def test_codegen_also_exits_4_on_a_database_that_cannot_be_opened(self, tmp_path: Path) -> None:
        """The sibling command maps the same failure onto the same code."""
        missing = tmp_path / "no-such-directory" / "analytics.db"
        result = runner.invoke(
            app,
            ["codegen", "sales_view", "--backend", "duckdb", "--database", str(missing)],
        )

        assert result.exit_code == EXIT_CONNECTION_ERROR, result.output
        assert result.exception is None or isinstance(result.exception, SystemExit), (
            f"a raw {type(result.exception).__name__} escaped the command"
        )
        assert "could not connect" in _diagnostics(result).lower(), result.stderr


PROBE_VIEW = "type_fidelity_view"
"""The view the file-backed fixture database carries, named directly by ``--view``."""

VIEW_ARGS = [
    "--view",
    PROBE_VIEW,
    "--metrics",
    "total_order_value,n_order_totals",
    "--dimensions",
    "region",
]
"""The ad-hoc equivalent of :data:`VALUE_BY_REGION`'s projection, as flags."""


class TestGeneratingFromAViewAndFieldList:
    """
    ``--view`` with ``--metrics`` / ``--dimensions``: a DTO with no model and no query module.

    The route exists to remove a bootstrapping cost, so what it must not do is import
    anything to pay it. That property has its own test below rather than being left implied,
    because nothing about the emitted class would reveal a stray import.
    """

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_view_and_fields_emit_a_dto_named_after_the_view(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """
        The class name is derived from the view when no ``--name`` was passed.

        The fields are asserted alongside it: a command that emitted the right class name
        over the wrong projection would satisfy a name-only check, and the projection is the
        thing ``--metrics`` and ``--dimensions`` exist to choose.
        """
        result = _invoke(type_fidelity_file_backed_db, *VIEW_ARGS)

        assert result.exit_code == 0, result.output
        classes = _class_defs(result.stdout)
        assert [node.name for node in classes] == ["TypeFidelityView"]
        assert [
            stmt.target.id
            for stmt in classes[0].body
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
        ] == ["total_order_value", "n_order_totals", "region"]

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_provenance_header_names_the_view_and_its_fields(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """
        There is no dotted path to record, so the header records what there is instead.

        A generated file that named only the view would leave a reader unable to tell which
        of its fields the class covers, which is the question the header answers for the
        dotted-path route by pointing at a query.
        """
        result = _invoke(type_fidelity_file_backed_db, *VIEW_ARGS)

        assert result.exit_code == 0, result.output
        assert f"view '{PROBE_VIEW}'" in result.stdout, result.stdout
        assert "metrics=[total_order_value, n_order_totals]" in result.stdout, result.stdout
        assert "dimensions=[region]" in result.stdout, result.stdout

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_repeated_and_comma_separated_options_mean_the_same_thing(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """
        ``--metrics a,b`` and ``--metrics a --metrics b`` produce byte-identical output.

        Both spellings are what people type — one by hand, one from a shell loop — and the
        equality is asserted over the whole emitted module so that neither the field order
        nor the header can differ between them.
        """
        comma = _invoke(type_fidelity_file_backed_db, *VIEW_ARGS)
        repeated = _invoke(
            type_fidelity_file_backed_db,
            "--view",
            PROBE_VIEW,
            "--metrics",
            "total_order_value",
            "--metrics",
            "n_order_totals",
            "--dimensions",
            "region",
        )

        assert repeated.exit_code == 0, repeated.output
        assert repeated.stdout == comma.stdout

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_name_flag_replaces_the_view_derived_class_name(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """``--name`` overrides the derived name on this route too, and the derived one goes."""
        result = _invoke(type_fidelity_file_backed_db, *VIEW_ARGS, "--name", "RegionTotals")

        assert result.exit_code == 0, result.output
        assert [node.name for node in _class_defs(result.stdout)] == ["RegionTotals"]

    def test_nothing_is_imported_to_generate_from_a_view(
        self, type_fidelity_file_backed_db: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The route that names no module must not reach the resolver that imports one.

        Poisoning ``resolve_query`` is what turns "imports nothing" into a measurement. The
        claim matters because importing a user's module is the one irreversible thing this
        command does — connections open, decorators fire — and a route documented as not
        doing it has to actually not do it.
        """
        from semolina.codegen import query_resolver

        def refuse(dotted_path: str) -> _Query:
            raise AssertionError(f"resolved a dotted path on the --view route: {dotted_path}")

        monkeypatch.setattr(query_resolver, "resolve_query", refuse)

        result = _invoke(type_fidelity_file_backed_db, *VIEW_ARGS)

        assert result.exit_code == 0, result.output

    def test_a_field_name_a_model_could_not_declare_exits_2_before_connecting(
        self, tmp_path: Path
    ) -> None:
        """
        Refused as an argument, not as a warehouse error.

        The ``--database`` path deliberately does not exist, so a command that validated the
        field name after building the engine would exit ``4`` instead. Ordering the check
        first is what keeps a typo from opening a connection.
        """
        missing = tmp_path / "no-such-directory" / "analytics.db"
        result = runner.invoke(
            app,
            [
                "codegen-dto",
                "--view",
                PROBE_VIEW,
                "--metrics",
                "limit",
                "--backend",
                "duckdb",
                "--database",
                str(missing),
            ],
        )

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "cannot be a field name" in _diagnostics(result), result.stderr
        assert result.stdout == "", result.stdout

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_misspelled_field_exits_6_naming_the_columns_the_view_really_has(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """
        A field the view does not carry is a warehouse-side failure, so it is ``6``.

        It is the likeliest mistake on this route — the field names are typed by hand rather
        than checked by an import — and the remedy is the list of columns that do exist,
        which the message carries.
        """
        result = _invoke(
            type_fidelity_file_backed_db,
            "--view",
            PROBE_VIEW,
            "--metrics",
            "total_order_valu",
            "--dimensions",
            "region",
        )

        assert result.exit_code == EXIT_PROBE_FAILED, result.output
        assert "total_order_value" in _diagnostics(result), result.stderr
        assert result.stdout == "", result.stdout

    def test_query_paths_and_view_cannot_be_combined(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """
        Two ways of saying which DTO to generate, given at once, has no defined meaning.

        Generating both would be an available answer and a wrong one: the flags read as
        narrowing the path, and a user who expected narrowing would get two classes instead.
        """
        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, *VIEW_ARGS)

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "cannot be combined" in _diagnostics(result), result.stderr
        assert result.stdout == "", result.stdout

    def test_field_options_without_a_view_are_refused(
        self, type_fidelity_file_backed_db: Path
    ) -> None:
        """``--metrics`` names fields *of* something, and on its own it names nothing."""
        result = _invoke(type_fidelity_file_backed_db, "--metrics", "total_order_value")

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "need --view" in _diagnostics(result), result.stderr


class TestWritingToAFile:
    """
    ``--output``: the same source, landed where a project keeps it.

    Redirecting stdout still works and is still tested above. What a flag adds is a
    destination a config file can declare, and one failure mode worth pinning: a run that
    fails must leave a previously generated file alone rather than truncating it.
    """

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_module_lands_in_the_file_and_not_on_stdout(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        Both halves: the file parses as the expected module, and stdout is empty.

        The empty stdout matters on its own. A command that wrote the file *and* echoed it
        would still pass a file-content check while doubling the output of any script that
        was also redirecting.
        """
        target = tmp_path / "dtos.py"
        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))

        assert result.exit_code == 0, result.output
        assert result.stdout == "", result.stdout
        assert [node.name for node in _class_defs(target.read_text())] == ["ValueByRegion"]
        assert "Wrote:" in _diagnostics(result), result.stderr

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_regenerating_replaces_the_file(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        The second run overwrites, so a DTO module can be regenerated in place.

        Appending is the failure an ``open(..., "a")`` would produce, and it stays valid
        Python — two identical classes, the second silently winning — which is precisely the
        shape that goes unnoticed.
        """
        target = tmp_path / "dtos.py"
        target.write_text("# stale\n")

        _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))
        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))

        assert result.exit_code == 0, result.output
        assert "# stale" not in target.read_text()
        assert [node.name for node in _class_defs(target.read_text())] == ["ValueByRegion"]

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_failed_run_leaves_the_previous_file_untouched(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        Rendering happens in full before anything is written, so a failure writes nothing.

        The failure used is the unbindable alias, which fires *after* every probe has
        succeeded — the latest point a run can still fail. An implementation that opened the
        destination early, or wrote per class, would have truncated the committed module by
        the time it got there.
        """
        import pyarrow

        from semolina.codegen import dto_renderer
        from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA

        target = tmp_path / "dtos.py"
        _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))
        good = target.read_text()

        with pytest.MonkeyPatch.context() as patch:

            def mislabelled_probe(
                engine: Any, query: _Query, *, class_name: str, origin: str
            ) -> dto_renderer.ProbedQuery:
                return dto_renderer.ProbedQuery(
                    class_name=class_name,
                    origin=origin,
                    query=query,
                    dialect=engine.dialect,
                    schema=pyarrow.schema([pyarrow.field("locale", pyarrow.string())]),
                    route=ROUTE_EXECUTE_SCHEMA,
                )

            patch.setattr(dto_renderer, "probe_query", mislabelled_probe)
            result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))

        assert result.exit_code == EXIT_PROBE_FAILED, result.output
        assert target.read_text() == good

    def test_a_directory_that_does_not_exist_exits_2_before_connecting(
        self, tmp_path: Path
    ) -> None:
        """
        A mistyped destination is caught before the warehouse is asked to type anything.

        The directory is not created, on purpose: a generated DTO is imported by the code
        that uses it, so its directory is a package that already exists, and creating one
        would turn a typo into a stray directory holding a module nothing imports.

        Checked before the engine is built — the ``--database`` path here does not exist
        either — so the exit code names the option the user got wrong rather than the
        connection that was never the problem.
        """
        result = runner.invoke(
            app,
            [
                "codegen-dto",
                VALUE_BY_REGION,
                "--backend",
                "duckdb",
                "--database",
                str(tmp_path / "no-such-directory" / "analytics.db"),
                "--output",
                str(tmp_path / "nope" / "dtos.py"),
            ],
        )

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "does not exist" in _diagnostics(result), result.stderr


def _write_config(tmp_path: Path, database: Path, body: str) -> Path:
    """
    Write a ``pyproject.toml`` declaring DTOs against the fixture database.

    Args:
        tmp_path: The project root to write into.
        database: The file-backed probe database, interpolated absolute so the config's own
            relative-path resolution is not what is under test here.
        body: The ``[[tool.semolina.dto.entries]]`` tables.

    Returns:
        The written path.
    """
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[project]\nname = "smoke"\n\n'
        "[tool.semolina.dto]\n"
        'backend = "duckdb"\n'
        f'database = "{database}"\n'
        'output = "dtos.py"\n\n' + body
    )
    return path


class TestGeneratingWhatTheProjectDeclares:
    """
    ``[tool.semolina.dto]``: the declared form of the other two routes.

    The command is run with **no arguments at all** in most of these, which is the whole
    ergonomic claim — a project that has written down its DTOs regenerates them with
    ``semolina codegen-dto`` and nothing else. ``monkeypatch.chdir`` stands in for being in
    the project root, because that is how the implicit ``pyproject.toml`` is found.
    """

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_both_entry_kinds_generate_into_one_file_in_declared_order(
        self,
        type_fidelity_file_backed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        A query entry and a view entry, one shared import block, the file's own order.

        Order is asserted because it is the thing a reviewer diffs when the file is
        regenerated: a run that sorted the classes would produce a large, meaningless diff
        the first time an entry was inserted anywhere but the end.
        """
        _write_config(
            tmp_path,
            type_fidelity_file_backed_db,
            "[[tool.semolina.dto.entries]]\n"
            f'query = "{VALUE_BY_REGION}"\n\n'
            "[[tool.semolina.dto.entries]]\n"
            'name = "RegionCounts"\n'
            f'view = "{PROBE_VIEW}"\n'
            'metrics = ["total_order_count"]\n'
            'dimensions = ["region"]\n',
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["codegen-dto"])

        assert result.exit_code == 0, result.output
        source = (tmp_path / "dtos.py").read_text()
        assert [node.name for node in _class_defs(source)] == ["ValueByRegion", "RegionCounts"]
        assert source.count("import pydantic") == 1, source

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_flag_overrides_the_declared_setting(
        self,
        type_fidelity_file_backed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        ``--output`` wins over the config's ``output``, and the declared file stays unwritten.

        Ordinary config precedence, and what makes the declared set of DTOs regenerable
        somewhere else — into a test fixture, say — without editing the file that declares
        them. The negative half is the load-bearing one: an implementation that honoured the
        flag *and* the config key would pass a check on the flag's file alone.
        """
        _write_config(
            tmp_path,
            type_fidelity_file_backed_db,
            f'[[tool.semolina.dto.entries]]\nquery = "{VALUE_BY_REGION}"\n',
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["codegen-dto", "--output", "elsewhere.py"])

        assert result.exit_code == 0, result.output
        assert (tmp_path / "elsewhere.py").is_file()
        assert not (tmp_path / "dtos.py").exists()

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_an_explicit_config_path_is_read_from_anywhere(
        self,
        type_fidelity_file_backed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        ``--config`` reads a file the working directory does not contain.

        The output path is asserted to land beside the *config*, not beside the cwd, which
        is the property that makes a declared destination mean one file rather than one per
        place the command is run from.
        """
        project = tmp_path / "project"
        project.mkdir()
        config = _write_config(
            project,
            type_fidelity_file_backed_db,
            f'[[tool.semolina.dto.entries]]\nquery = "{VALUE_BY_REGION}"\n',
        )
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        result = runner.invoke(app, ["codegen-dto", "--config", str(config)])

        assert result.exit_code == 0, result.output
        assert (project / "dtos.py").is_file()
        assert not (elsewhere / "dtos.py").exists()

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_two_entries_generating_the_same_class_name_are_refused(
        self,
        type_fidelity_file_backed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        One file cannot carry two classes of one name, and Python will not say so.

        The second definition silently replaces the first, so the config would appear to
        declare two DTOs and generate one. Declaring the same view twice — with different
        field lists, to cover two use sites — is the ordinary way to reach it, and the
        remedy is the ``name`` key, which the message points at.
        """
        _write_config(
            tmp_path,
            type_fidelity_file_backed_db,
            "[[tool.semolina.dto.entries]]\n"
            f'view = "{PROBE_VIEW}"\n'
            'metrics = ["total_order_value"]\n\n'
            "[[tool.semolina.dto.entries]]\n"
            f'view = "{PROBE_VIEW}"\n'
            'dimensions = ["region"]\n',
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["codegen-dto"])

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "one file cannot carry two" in _diagnostics(result), result.stderr
        assert not (tmp_path / "dtos.py").exists()

    def test_a_malformed_section_exits_2_naming_the_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A typo in the config is a bad option, reported the way a bad flag is."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.semolina.dto]\n"
            'backend = "duckdb"\n'
            "[[tool.semolina.dto.entries]]\n"
            f'view = "{PROBE_VIEW}"\n'
            'metric = ["total_order_value"]\n'
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["codegen-dto"])

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "'metric'" in _diagnostics(result), result.stderr

    def test_a_config_path_that_does_not_exist_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        An explicit ``--config`` is a claim the file is there, unlike the implicit lookup.

        Falling back to ``./pyproject.toml`` would be worse than refusing: the command would
        generate a *different* project's DTOs and report success.
        """
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["codegen-dto", "--config", "no-such-file.toml"])

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "does not exist" in _diagnostics(result), result.stderr

    def test_a_project_declaring_nothing_names_all_three_routes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The bare command with nothing to do explains every way to give it something.

        This is the message a first-time user reaches by typing the command name alone, so
        it names the two flag routes as well as the config — someone who mistyped a dotted
        path badly enough for it to vanish should not be told to write a config section.
        """
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["codegen-dto"])

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        diagnostics = _diagnostics(result)
        assert "Nothing to generate" in diagnostics, result.stderr
        assert "--view" in diagnostics, result.stderr
        assert "[tool.semolina.dto]" in diagnostics, result.stderr

    def test_a_config_naming_no_backend_says_so(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        ``--backend`` is required unless the section supplies it, and the message says both.

        A section may legitimately omit it — the file says which DTOs exist, the command
        line says where to probe them — so the omission has to report as a missing option
        rather than as a malformed config.
        """
        (tmp_path / "pyproject.toml").write_text(
            f'[[tool.semolina.dto.entries]]\nquery = "{VALUE_BY_REGION}"\n'
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["codegen-dto"])

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "No backend" in _diagnostics(result), result.stderr

    def test_a_config_run_cannot_be_combined_with_a_query_path(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        ``--config`` generates what a project declares, so an extra path has no place in it.

        Appending the path to the declared set is the available wrong answer: the config
        would then generate a file it does not describe, which is the one thing a checked-in
        declaration is for.
        """
        config = _write_config(
            tmp_path,
            type_fidelity_file_backed_db,
            f'[[tool.semolina.dto.entries]]\nquery = "{VALUE_BY_REGION}"\n',
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["codegen-dto", COUNTS_BY_REGION, "--config", str(config)])

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "cannot be combined" in _diagnostics(result), result.stderr


class TestTheSectionNameSurvivesRichMarkup:
    """
    ``[tool.semolina.dto]`` in help text is a rich style tag unless it is escaped.

    Typer renders help and epilogs through rich with markup on, and rich reads a bracketed
    word as a tag and removes it. The section name is the one string this command's help has
    to print that looks exactly like one, so it vanished from ``--help`` entirely: the
    ``--backend`` line read "Required unless  sets it." and the exit-code table described "a
    malformed  section". Measured 2026-08-16.

    The same string reaches *stderr* through ``_labelled``, which wraps it in a
    :class:`~rich.text.Text` and bypasses the parser — which is why the error-message tests
    above passed against the broken help.
    """

    def test_help_names_the_section_a_config_goes_in(self) -> None:
        """
        The three places the section name appears in ``--help``, checked by count.

        By count rather than by presence: the command docstring, the ``--backend`` help and
        the ``--config`` help each name it, and an escape applied to only one of them would
        satisfy a substring check while leaving the other two blank.
        """
        result = runner.invoke(app, ["codegen-dto", "--help"])

        assert result.exit_code == 0, result.output
        assert result.output.count("[tool.semolina.dto]") >= 3, result.output

    def test_the_exit_code_epilog_names_the_section_too(self) -> None:
        """
        The epilog is registered separately in :mod:`semolina.cli`, so it escapes separately.

        It is also the table ``docs/src/how-to/dto-codegen.rst`` is required to agree with,
        and a row that silently lost two words would make the two disagree with nothing to
        notice it.
        """
        result = runner.invoke(app, ["codegen-dto", "--help"])

        assert "malformed [tool.semolina.dto] section" in " ".join(result.output.split()), (
            result.output
        )


class TestCheckingACommittedFile:
    """
    ``--check``: the CI half, and the reason exit 5 is now reachable on this command.

    The sibling reads a ``--model PATH``; this one reads the file ``--output`` names, so a
    project that declares ``output`` in its config verifies exactly the file a bare
    ``semolina codegen-dto`` would write, with no second path to keep in step. Every test
    below therefore generates first and checks second, which is also how the workflow reads.
    """

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_freshly_generated_file_reports_no_drift(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        Generate, then check, and get exit 0.

        The green path is the one that has to stay green: a check that cried drift on its
        own output would be switched off within a day, and every later assertion here would
        be worthless.
        """
        target = tmp_path / "dtos.py"
        _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))

        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))

        assert result.exit_code == 0, result.output
        check = _invoke(
            type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target), "--check"
        )

        assert check.exit_code == 0, check.output
        assert "match" in _diagnostics(check), check.stderr

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_check_writes_nothing_to_stdout_and_does_not_touch_the_file(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        A check reports; it does not regenerate.

        Both halves matter. Source on stdout would corrupt a ``> file`` redirect in a
        pipeline that also generates, and a check that rewrote its target would make CI
        green by editing the thing under test -- the failure mode that makes a drift check
        worse than none.
        """
        target = tmp_path / "dtos.py"
        _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))
        before = target.read_text()

        result = _invoke(
            type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target), "--check"
        )

        assert result.exit_code == 0, result.output
        assert result.stdout == "", result.stdout
        assert target.read_text() == before

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_changed_annotation_exits_5(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        5, the sibling's drift code, now reachable here for the same meaning.

        Distinct from 1 on purpose: a CI job that cannot tell "your DTO is stale" from
        "codegen crashed" has to treat both the same, which means either failing builds on a
        crash or shipping stale DTOs on a real drift.
        """
        target = tmp_path / "dtos.py"
        _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))
        target.write_text(
            target.read_text().replace("n_order_totals: int", "n_order_totals: float")
        )

        result = _invoke(
            type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target), "--check"
        )

        assert result.exit_code == 5, result.output
        assert "drift" in _diagnostics(result), result.stderr
        assert result.stdout == "", result.stdout

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_changed_alias_exits_5(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        The half the sibling has no equivalent for, driven through the published command.

        An alias moves when a metric is renamed and when the file was generated against a
        different backend, and only the second is likely -- so this is the check that
        catches a Snowflake DTO committed into a Databricks deployment.
        """
        target = tmp_path / "dtos.py"
        _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))
        target.write_text(
            target.read_text().replace('validation_alias="region"', 'validation_alias="REGION"')
        )

        result = _invoke(
            type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target), "--check"
        )

        assert result.exit_code == 5, result.output
        assert "alias differs" in _diagnostics(result), result.stderr

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_missing_class_is_reported_by_name(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        A renamed class reads as both a missing one and an extra one, and says so.

        The pair is the useful report. "Missing" alone would send the reader to regenerate;
        naming the leftover as well tells them what the file has instead, which is usually
        the answer.
        """
        target = tmp_path / "dtos.py"
        _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target))
        target.write_text(target.read_text().replace("class ValueByRegion", "class Renamed"))

        result = _invoke(
            type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target), "--check"
        )

        assert result.exit_code == 5, result.output
        diagnostics = _diagnostics(result)
        assert "ValueByRegion" in diagnostics, result.stderr
        assert "Renamed" in diagnostics, result.stderr

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_a_leftover_class_the_config_no_longer_declares_exits_5(
        self,
        type_fidelity_file_backed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Removing an entry from the config does not remove its class from the file.

        The leftover still imports and still type-checks, and describes nothing. Only a
        whole-file check can see it, which is the argument for checking the module rather
        than each class in isolation.
        """
        _write_config(
            tmp_path,
            type_fidelity_file_backed_db,
            f'[[tool.semolina.dto.entries]]\nquery = "{VALUE_BY_REGION}"\n\n'
            f'[[tool.semolina.dto.entries]]\nquery = "{COUNTS_BY_REGION}"\n',
        )
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["codegen-dto"])

        _write_config(
            tmp_path,
            type_fidelity_file_backed_db,
            f'[[tool.semolina.dto.entries]]\nquery = "{VALUE_BY_REGION}"\n',
        )
        result = runner.invoke(app, ["codegen-dto", "--check"])

        assert result.exit_code == 5, result.output
        assert "CountsByRegion" in _diagnostics(result), result.stderr

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_the_config_declared_output_is_what_gets_checked(
        self,
        type_fidelity_file_backed_db: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        ``semolina codegen-dto --check`` with no other flag is the CI invocation.

        It has to resolve the same file the bare generate command writes, or the two would
        drift apart and the check would verify a file nobody deploys.
        """
        _write_config(
            tmp_path,
            type_fidelity_file_backed_db,
            f'[[tool.semolina.dto.entries]]\nquery = "{VALUE_BY_REGION}"\n',
        )
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["codegen-dto"])

        result = runner.invoke(app, ["codegen-dto", "--check"])

        assert result.exit_code == 0, result.output
        assert (tmp_path / "dtos.py").is_file()

    def test_check_without_a_destination_exits_2(self, type_fidelity_file_backed_db: Path) -> None:
        """
        ``--check`` with neither ``--output`` nor a config ``output`` names no file.

        A coupled-flag error, reported the way this CLI reports every other one, rather than
        a check that silently compared against nothing and passed.
        """
        result = _invoke(type_fidelity_file_backed_db, VALUE_BY_REGION, "--check")

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "--output" in _diagnostics(result), result.stderr

    def test_check_against_a_file_that_does_not_exist_exits_2(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        A missing target is the caller's mistake, not drift.

        Reporting 5 would tell a CI job the committed DTO is stale when the truth is that
        nobody has generated it yet, and the remedy is different.
        """
        result = _invoke(
            type_fidelity_file_backed_db,
            VALUE_BY_REGION,
            "--output",
            str(tmp_path / "never-generated.py"),
            "--check",
        )

        assert result.exit_code == EXIT_INVALID_BACKEND, result.output
        assert "no such file" in _diagnostics(result), result.stderr

    @pytest.mark.usefixtures("data_fetch_guard")
    def test_an_unparseable_committed_file_exits_1(
        self, type_fidelity_file_backed_db: Path, tmp_path: Path
    ) -> None:
        """
        1, not 5: nothing was compared, so calling it drift reports a verdict never reached.

        Mirrors how the sibling treats an unreadable ``--model`` file.
        """
        target = tmp_path / "dtos.py"
        target.write_text("class Broken(:\n")

        result = _invoke(
            type_fidelity_file_backed_db, VALUE_BY_REGION, "--output", str(target), "--check"
        )

        assert result.exit_code == 1, result.output
        assert "Cannot parse" in _diagnostics(result), result.stderr
