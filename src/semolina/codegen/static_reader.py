"""
Read a committed file's names, base classes and constants without importing it.

Both ``--check`` commands read a file the user points at: a committed model module, or a
committed DTO module. Decision D9 (2026-10-15) settled how. The file is **parsed, never
imported**, so nothing in it runs, and `griffe <https://mkdocstrings.github.io/griffe/>`_
(the ``griffelib`` distribution) supplies what plain :func:`ast.parse` lacks:

* every name a statement uses resolves through the file's own imports, so
  ``from semolina import Metric as M`` makes ``M[int]()`` a metric and
  ``from decimal import Decimal`` makes ``Decimal`` the ``decimal.Decimal`` codegen writes;
* a base class is followed into the module that declares it, in the same file or another,
  so inherited fields are read rather than reported as absent;
* ``view=VIEW_NAME`` finds the string constant ``VIEW_NAME`` names, wherever it lives.

griffe parses each module it needs from source. ``allow_inspection=False`` forbids it from
ever falling back to importing one, and its search path is the file's own package root and
the working directory, never ``sys.path``. A module outside those (``semolina`` itself, the
standard library, a third-party package) is never read: names imported from it resolve to
their qualified name through the import statement alone.

Statements are still read from :mod:`ast` nodes by the two readers,
:mod:`semolina.codegen.model_reader` and :mod:`semolina.codegen.dto_reader`, because they
must see every statement in a class body, including the ones they cannot interpret. That is
what lets them warn about a field-like statement instead of dropping it (GEN-12). This
module gives them the resolution: :class:`StaticModule` loads the file, and its methods
answer "what does this name refer to", "which classes does this class inherit fields from"
and "what string does this constant hold".
"""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import griffe

if TYPE_CHECKING:
    from collections.abc import Iterator

    from semolina.codegen.type_compare import Resolver

__all__ = [
    "UNFOLLOWED_BASE_PREFIXES",
    "STAR_IMPORTED_CHAIN_ENDS",
    "walk_statement",
    "ClassSource",
    "StaticModule",
]


_MAX_HOPS = 10
"""How many constant-to-constant hops ``view=`` may take before the reader gives up."""

UNFOLLOWED_BASE_PREFIXES = (
    "builtins.",
    "typing.",
    "typing_extensions.",
    "abc.",
    "semolina.",
    "pydantic.",
)
"""
Base classes that are never followed, because they cannot declare a generated field.

``semolina.SemanticView`` and ``pydantic.BaseModel`` end every chain. ``typing.Generic``,
``abc.ABC`` and ``object`` declare nothing a check compares.
"""

STAR_IMPORTED_CHAIN_ENDS = frozenset({"SemanticView", "BaseModel", "Generic", "Protocol", "ABC"})
"""
Chain-ending bases a star import from one of :data:`UNFOLLOWED_BASE_PREFIXES` can bring in.

A star import is not followed, so these names stay unresolved; they are recognised by name.
"""


def walk_statement(statement: ast.AST) -> Iterator[ast.AST]:
    """
    Walk a statement without descending into a ``def`` or ``class`` nested inside it.

    Args:
        statement: A statement from a class body, or an expression in one.

    Yields:
        Each node of the statement, outside any nested function or class body.
    """
    pending: list[ast.AST] = [statement]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(
            child
            for child in ast.iter_child_nodes(node)
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )


def _package_root(path: Path) -> tuple[Path, str]:
    """
    Find the directory a file's top-level package lives in, and the file's dotted name.

    Walks up from the file while each directory holds an ``__init__.py``, which is how
    Python itself sees a regular package. A ``src/`` layout therefore needs no
    configuration: ``src/app/models.py`` inside the package ``app`` is ``app.models``, with
    ``src`` as its root. A namespace package (no ``__init__.py``) is not recognised: the
    file's own directory becomes the root, so its imports from that package resolve only
    when you run the command from the directory that contains the package.

    Args:
        path: An absolute path to a Python file.

    Returns:
        The root directory, and the module's dotted name relative to it.
    """
    parts = [path.stem]
    directory = path.parent
    while (directory / "__init__.py").is_file() and directory.parent != directory:
        parts.insert(0, directory.name)
        directory = directory.parent
    if parts[-1] == "__init__":
        parts.pop()
    return directory, ".".join(parts)


@dataclass(frozen=True)
class ClassSource:
    """
    One class in an inheritance chain: its syntax tree and the scope its names resolve in.

    Attributes:
        node: The class definition.
        scope: The griffe object the class body's names resolve through: the class itself,
            or its module when griffe holds no separate object for it.
        label: How a warning names the class (its qualified name).
    """

    node: ast.ClassDef
    scope: griffe.Object | griffe.Alias
    label: str


@dataclass
class StaticModule:
    """
    A committed file, loaded by griffe for name resolution, alongside its syntax tree.

    Build one with :meth:`load`. The file's source has already been read and parsed by the
    caller, so a missing file or a syntax error is reported in the caller's own words before
    griffe is involved.

    Attributes:
        path: The file, resolved to an absolute path.
        tree: The file's syntax tree.
        module: The griffe module for the file.
        loader: The griffe loader, which loads further modules from the search paths on
            demand.
    """

    path: Path
    tree: ast.Module
    module: griffe.Module
    loader: griffe.GriffeLoader
    _trees: dict[Path, ast.Module | None] = field(default_factory=dict[Path, "ast.Module | None"])
    _attempted: set[str] = field(default_factory=set[str])

    @classmethod
    def load(cls, path: Path, source: str, tree: ast.Module) -> StaticModule:
        """
        Load a parsed file through griffe.

        The file is loaded under the dotted name its package layout gives it, so relative
        imports and imports of its sibling modules resolve. When griffe finds some other
        file under that name (the file shadowed by a package of the same name, say), or
        finds none (a file without a ``.py`` suffix), the source is visited on its own
        under its file name instead: names, same-file bases and same-file constants still
        resolve, and only imports from its own package are lost.

        Args:
            path: The file.
            source: The file's text, already read.
            tree: The file's syntax tree, already parsed.

        Returns:
            The loaded module.
        """
        path = path.resolve()
        root, name = _package_root(path)
        search_paths = list(dict.fromkeys([root, Path.cwd().resolve()]))
        loader = griffe.GriffeLoader(search_paths=search_paths, allow_inspection=False)
        module: griffe.Module | None = None
        with griffe.logger.disable():
            try:
                loaded = loader.load(name)
            except Exception:  # noqa: BLE001 - any failure here falls back to visiting the source
                loaded = None
            if isinstance(loaded, griffe.Module) and loaded.filepath == path:
                module = loaded
            else:
                # A dotted key is a path to griffe's collection: `models.v2` would be looked
                # up under a `models` that is not there. The stand-alone name has no dots.
                module = griffe.visit(
                    path.stem.replace(".", "_"),
                    filepath=path,
                    code=source,
                    modules_collection=loader.modules_collection,
                    lines_collection=loader.lines_collection,
                )
                loader.modules_collection.set_member(module.name, module)
        static = cls(path=path, tree=tree, module=module, loader=loader)
        static._trees[path] = tree
        return static

    def resolver(self, scope: griffe.Object | griffe.Alias) -> Resolver:
        """
        Build a resolver for names used inside ``scope``.

        Args:
            scope: A griffe object: a module, or a class whose body uses the names, which
                resolve in the class's module.

        Returns:
            A function mapping a bare name to its qualified name, falling back to the
            builtins, or None when the name is unknown.
        """

        # A class body's names are evaluated in the enclosing module: `date = Dimension[date]()`
        # reads the imported `date`, which the class's own `date` does not exist yet to hide.
        # griffe's class scope would look the class's members up first.
        module_scope = scope.parent if scope.is_class and scope.parent is not None else scope

        def resolve(name: str) -> str | None:
            try:
                return self.final_path(module_scope.resolve(name))
            except (griffe.NameResolutionError, griffe.AliasResolutionError):
                return f"builtins.{name}" if hasattr(builtins, name) else None

        return resolve

    def qualname(self, node: ast.expr, scope: griffe.Object | griffe.Alias) -> str | None:
        """
        Resolve a name or dotted name in ``scope`` to its qualified name.

        Args:
            node: A ``Name`` or ``Attribute`` chain.
            scope: Where the expression appears.

        Returns:
            The qualified name, or None when the expression is not a (dotted) name or its
            leftmost name does not resolve.
        """
        if isinstance(node, ast.Name):
            return self.resolver(scope)(node.id)
        if isinstance(node, ast.Attribute):
            head = self.qualname(node.value, scope)
            return None if head is None else self.final_path(f"{head}.{node.attr}")
        return None

    def final_path(self, qualname: str) -> str:
        """
        Follow re-exports to the path a name was defined under.

        ``from app.compat import Metric``, where ``app/compat.py`` imports it from semolina,
        resolves to ``app.compat.Metric``; this follows it on to ``semolina.Metric``. Only
        packages on the search path are loaded, so the chain stops at the first module
        outside it (semolina itself, the standard library), which is the path wanted.

        Args:
            qualname: A qualified name.

        Returns:
            The path the last alias on the search path points at, or ``qualname`` itself.
        """
        path = qualname
        for _ in range(_MAX_HOPS):
            try:
                found = self.loader.modules_collection.get_member(path)
            except KeyError:
                if self._load_package_of(path):
                    continue
                return path
            except (griffe.AliasResolutionError, griffe.CyclicAliasError):
                return path
            if not isinstance(found, griffe.Alias):
                return path
            path = found.target_path
        return path

    def class_scope(self, node: ast.ClassDef) -> griffe.Object | griffe.Alias:
        """
        Find the griffe object a top-level class of this file resolves its names through.

        Args:
            node: A class defined at the top level of this file.

        Returns:
            griffe's object for the class, or the module when griffe holds a different
            object under that name (a later class of the same name replaces an earlier one).
        """
        member = self.module.members.get(node.name)
        if member is not None and not member.is_alias and member.lineno == node.lineno:
            return member
        return self.module

    def lookup(self, qualname: str) -> griffe.Object | None:
        """
        Find the object a qualified name refers to, loading its package when needed.

        Only packages on the search path are loaded (the file's package root and the
        working directory), each at most once, and only by parsing.

        Args:
            qualname: A fully qualified name, e.g. ``'app.names.VIEW_NAME'``.

        Returns:
            The object, with aliases followed to their target, or None when it cannot be
            found on the search path.
        """
        for _ in range(_MAX_HOPS):
            try:
                found = self.loader.modules_collection.get_member(qualname)
                return found.final_target if isinstance(found, griffe.Alias) else found
            except KeyError:
                missing = qualname
            except griffe.AliasResolutionError as e:
                missing = e.alias.target_path
            except griffe.CyclicAliasError:
                return None
            if not self._load_package_of(missing):
                return None
        return None

    def _load_package_of(self, qualname: str) -> bool:
        """
        Load the top-level package a qualified name lives in, once.

        Args:
            qualname: A qualified name.

        Returns:
            True when a package was newly loaded, so a lookup is worth retrying.
        """
        top = qualname.split(".", 1)[0]
        if top in self._attempted or top in self.loader.modules_collection.members:
            return False
        self._attempted.add(top)
        with griffe.logger.disable():
            try:
                self.loader.load(top)
            except Exception:  # noqa: BLE001 - not on the search path, or not loadable
                return False
        return True

    def string_constant(self, node: ast.expr, scope: griffe.Object | griffe.Alias) -> str | None:
        """
        Read a string: a literal, or a name or dotted name bound to a string constant.

        Args:
            node: The expression, e.g. the value of a ``view=`` keyword.
            scope: Where the expression appears.

        Returns:
            The string, or None when the expression is not a string or a constant holding
            one.
        """
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        qualname = self.qualname(node, scope)
        for _ in range(_MAX_HOPS):
            if qualname is None:
                return None
            target = self.lookup(qualname)
            if not isinstance(target, griffe.Attribute):
                return None
            value = target.value
            if isinstance(value, str):
                try:
                    literal = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    return None
                return literal if isinstance(literal, str) else None
            if isinstance(value, (griffe.ExprName, griffe.ExprAttribute)):
                # A constant bound to another constant: follow it.
                qualname = value.canonical_path
                continue
            return None
        return None

    def _tree_of(self, path: Path) -> ast.Module | None:
        """
        Parse a module griffe found, once.

        Args:
            path: The module's file.

        Returns:
            Its syntax tree, or None when it cannot be read or parsed.
        """
        if path not in self._trees:
            try:
                self._trees[path] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError, ValueError):
                self._trees[path] = None
        return self._trees[path]

    def _class_source(self, target: griffe.Class) -> ClassSource | None:
        """
        Find the syntax tree of a class griffe found.

        Args:
            target: The class.

        Returns:
            Its source, or None when its file cannot be parsed or holds no such class.
        """
        filepath = target.filepath
        if not isinstance(filepath, Path):
            return None
        tree = self._tree_of(filepath.resolve())
        if tree is None:
            return None
        candidates = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == target.name
        ]
        exact = [node for node in candidates if node.lineno == target.lineno]
        chosen = (exact or candidates or [None])[0]
        if chosen is None:
            return None
        return ClassSource(node=chosen, scope=target, label=target.path)

    def _bases(self, cls: ClassSource, warnings: list[str]) -> list[ClassSource]:
        """
        Resolve a class's bases to the ones whose fields count.

        Args:
            cls: The class.
            warnings: Receives one line per base that could not be followed.

        Returns:
            The bases to follow, in declaration order.
        """
        bases: list[ClassSource] = []
        for base in cls.node.bases:
            # `Generic[T]` is a subscript of the base it names.
            named = base.value if isinstance(base, ast.Subscript) else base
            qualname = self.qualname(named, cls.scope)
            if qualname is not None and qualname.startswith(UNFOLLOWED_BASE_PREFIXES):
                continue
            if qualname is None and self._star_imported_chain_end(named, cls):
                continue
            target = None if qualname is None else self.lookup(qualname)
            source = self._class_source(target) if isinstance(target, griffe.Class) else None
            if source is not None and source.node is cls.node and isinstance(named, ast.Name):
                # `class Sales(Sales)`: the base is the imported `Sales`, bound before this
                # class replaced it, but griffe keeps only the module's last binding.
                imported = self._imported_path(named.id, cls)
                target = None if imported is None else self.lookup(imported)
                source = self._class_source(target) if isinstance(target, griffe.Class) else None
            if source is None:
                warnings.append(
                    f"{cls.label}: base class {ast.unparse(base)} was not followed, so "
                    "any field it declares reads as absent"
                )
                continue
            bases.append(source)
        return bases

    def _imported_path(self, name: str, cls: ClassSource) -> str | None:
        """
        Find what a top-level import in a class's own file binds a name to.

        Args:
            name: The bound name.
            cls: The class whose file is searched.

        Returns:
            The imported object's qualified name, re-exports followed, or None when no
            import in the file binds ``name``.
        """
        filepath = cls.scope.filepath
        tree = self._tree_of(filepath.resolve()) if isinstance(filepath, Path) else None
        if tree is None:
            return None
        module = cls.scope.module.path
        package = module if cls.scope.module.is_package else module.rpartition(".")[0]
        for stmt in tree.body:
            if isinstance(stmt, ast.ImportFrom):
                if stmt.level:
                    parts = package.split(".")
                    base = ".".join(parts[: len(parts) - stmt.level + 1])
                    source = ".".join(p for p in (base, stmt.module) if p)
                else:
                    source = stmt.module or ""
                for alias in stmt.names:
                    if (alias.asname or alias.name) == name:
                        return self.final_path(f"{source}.{alias.name}")
        return None

    def _star_imported_chain_end(self, node: ast.expr, cls: ClassSource) -> bool:
        """
        Whether an unresolved base is a chain-ending name a star import brought in.

        ``from semolina import *`` leaves ``SemanticView`` unresolvable without importing
        anything, so a bare name from :data:`STAR_IMPORTED_CHAIN_ENDS` counts as the base
        it ends a chain with, when the file star-imports one of the modules those come from.

        Args:
            node: The base expression, its subscript removed.
            cls: The class it is a base of, whose own file's imports are the ones that count.

        Returns:
            ``True`` when the base should be skipped without a warning.
        """
        if not isinstance(node, ast.Name) or node.id not in STAR_IMPORTED_CHAIN_ENDS:
            return False
        filepath = cls.scope.filepath
        tree = self._tree_of(filepath.resolve()) if isinstance(filepath, Path) else None
        if tree is None:
            return False
        return any(
            isinstance(stmt, ast.ImportFrom)
            and stmt.level == 0
            and stmt.module is not None
            and f"{stmt.module}.".startswith(UNFOLLOWED_BASE_PREFIXES)
            and any(alias.name == "*" for alias in stmt.names)
            for stmt in tree.body
        )

    def inheritance_chain(self, cls: ClassSource, warnings: list[str]) -> list[ClassSource]:
        """
        List a class and the bases it inherits fields from, in method resolution order.

        Bases that end a chain (:data:`UNFOLLOWED_BASE_PREFIXES`) are left out without a
        word. Any other base that cannot be found is left out with a warning, so its fields
        read as absent and the reason is printed beside the report.

        Args:
            cls: The class.
            warnings: Receives one line per base that could not be followed.

        Returns:
            The class first, then its bases in the order Python would look them up. Read
            them in reverse to let a subclass's declaration replace its base's.
        """

        def key(source: ClassSource) -> tuple[str, int]:
            return source.label, source.node.lineno

        def linearize(source: ClassSource, seen: tuple[tuple[str, int], ...]) -> list[ClassSource]:
            if key(source) in seen:
                raise ValueError(f"inheritance cycle through {source.label}")
            bases = self._bases(source, warnings)
            sequences = [linearize(base, (*seen, key(source))) for base in bases]
            sequences.append(list(bases))
            result = [source]
            while any(sequences):
                sequences = [s for s in sequences if s]
                for sequence in sequences:
                    head = sequence[0]
                    if not any(key(head) in map(key, s[1:]) for s in sequences):
                        break
                else:
                    raise ValueError(f"no consistent method resolution order for {source.label}")
                result.append(head)
                sequences = [s[1:] if key(s[0]) == key(head) else s for s in sequences]
            return result

        try:
            return linearize(cls, ())
        except ValueError as e:
            warnings.append(f"{cls.node.name}: base classes were not followed ({e})")
            return [cls]
