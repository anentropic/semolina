"""
Importable fixture modules for the codegen tests.

A package rather than loose files so the modules inside have real dotted import paths.
``tests/unit/codegen/__init__.py`` makes ``tests/unit`` the import root under pytest's
default ``prepend`` mode, so this package is reachable as ``codegen.fixtures`` — which is
what lets ``tests/unit/codegen/test_dto_cli.py`` hand the DTO codegen CLI a dotted path that
genuinely resolves instead of one stitched together with ``monkeypatch``.
"""
