"""Generate API reference pages for all Cubano modules."""

from pathlib import Path

import mkdocs_gen_files


def main():
    src = Path("src")
    nav = mkdocs_gen_files.Nav()

    for path in sorted(src.rglob("*.py")):
        module_path = path.relative_to(src).with_suffix("")
        doc_path = path.relative_to(src).with_suffix(".md")
        full_doc_path = Path("reference", doc_path)

        parts = tuple(module_path.parts)

        # Skip __init__, __main__, conftest, and private modules
        if parts[-1] in ("__init__", "__main__", "conftest"):
            continue
        if any(part.startswith("_") for part in parts):
            continue

        nav[parts] = doc_path.as_posix()

        with mkdocs_gen_files.open(full_doc_path, "w") as fd:
            ident = ".".join(parts)
            fd.write(f"# `{ident}`\n\n::: {ident}\n")

        mkdocs_gen_files.set_edit_path(full_doc_path, path)

    # Write reference index so reference/ URL resolves
    with mkdocs_gen_files.open("reference/index.md", "w") as fd:
        fd.write("# API Reference\n\n")
        fd.write("Auto-generated documentation for all public Cubano modules.\n")

    with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
        nav_file.write("* [API Reference](index.md)\n")
        nav_file.writelines(nav.build_literate_nav())


main()
