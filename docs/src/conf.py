"""Sphinx configuration for Semolina documentation."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

project = "Semolina"
copyright = "2026, Anentropic"
author = "Anentropic"

# Read from installed package metadata so pages can cite the version via ``|release|``
# instead of hardcoding one that goes stale at the next release.
try:
    release = _package_version("semolina")
except PackageNotFoundError:  # editable checkout without installed metadata
    release = "0.0.0+unknown"
version = release

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_design",
    "autoapi.extension",
]

exclude_patterns = ["_build"]

# Every cross-reference must resolve. This is what keeps hand-written pages honest: without
# it, a ref to a path that does not exist renders as unlinked plain text and the build stays
# green, which is how 131 dead refs to re-export paths (``semolina.SemanticView`` rather than
# ``semolina.models.SemanticView``) accumulated unnoticed.
nitpicky = True

# Targets that cannot resolve and are not defects. Everything here is either a third-party
# object with no published inventory, a typing artifact autoapi renders as a type, or a
# private name autoapi deliberately does not document. Anything NOT matching these is a real
# broken reference and fails the build.
# Sphinx matches these with ``re.fullmatch``, so each pattern must describe the whole target.
nitpick_ignore_regex = [
    # Third-party objects with no intersphinx inventory. pyarrow is mapped below instead;
    # adbc-drivers publishes an inventory but serves it 403 to non-browser clients.
    ("py:.*", r"(pandas|polars|typer|rich|pydantic|adbc_driver_manager)\..*"),
    # Typing artifacts and dunders that appear in signatures but are not documentable targets.
    ("py:.*", r"Ellipsis|T|_M|__del__"),
    # Private names: autoapi_options omits ``private-members``, so these are never emitted.
    ("py:.*", r"(\w+\.)*_\w+"),
    # Module-level type alias; autoapi emits it as py:data, so a py:class ref cannot match.
    ("py:class", r"WarehouseConfig"),
]

# Suppress warnings from autoapi-generated pages:
# - docutils: source docstrings use markdown-style backticks (legacy from mkdocstrings era)
# - autoapi.python_import_resolution: unresolvable type references in stubs
# - misc.highlighting_failure: Databricks $$ metric view syntax isn't standard SQL
suppress_warnings = [
    "docutils",
    "autoapi.python_import_resolution",
    "misc.highlighting_failure",
]

# -- Napoleon (Google-style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_rtype = False

# -- AutoAPI
autoapi_dirs = ["../../src/semolina"]
autoapi_type = "python"
autoapi_root = "reference/api"
autoapi_options = [
    "members",
    "show-inheritance",
    "show-module-summary",
]
autoapi_ignore = ["*conftest*", "*__main__*"]
autoapi_python_class_content = "class"
autoapi_member_order = "bysource"
autoapi_add_toctree_entry = False

# -- Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pyarrow": ("https://arrow.apache.org/docs", None),
}

# -- HTML output
html_theme = "shibuya"
html_title = "Semolina"
html_baseurl = "https://anentropic.github.io/semolina/"

html_static_path = ["_static"]
templates_path = ["_templates"]

html_css_files = [
    "css/s-layer.css",
]

html_copy_source = False
html_show_sourcelink = False

html_theme_options = {
    "accent_color": "orange",
    "github_url": "https://github.com/anentropic/semolina",
    "globaltoc_expand_depth": 1,
    "nav_links": [
        {"title": "Home", "url": "index"},
        {
            "title": "Tutorials",
            "url": "tutorials/index",
            "children": [
                {"title": "Installation", "url": "tutorials/installation"},
                {"title": "Your first query", "url": "tutorials/first-query"},
            ],
        },
        {
            "title": "How-To Guides",
            "url": "how-to/index",
            "children": [
                {
                    "title": "How to choose and configure a backend",
                    "url": "how-to/backends/overview",
                },
                {"title": "How to connect to Snowflake", "url": "how-to/backends/snowflake"},
                {"title": "How to connect to Databricks", "url": "how-to/backends/databricks"},
                {"title": "How to connect to DuckDB", "url": "how-to/backends/duckdb"},
                {
                    "title": "How to set up connection pools for production",
                    "url": "how-to/connection-pools",
                },
                {"title": "How to define models", "url": "how-to/models"},
                {"title": "How to build queries", "url": "how-to/queries"},
                {"title": "How to filter queries", "url": "how-to/filtering"},
                {"title": "How to order and limit results", "url": "how-to/ordering"},
                {
                    "title": "How to serialize results for API responses",
                    "url": "how-to/serialization",
                },
                {
                    "title": "How to retrieve results as Arrow tables",
                    "url": "how-to/arrow-output",
                },
                {
                    "title": "How to generate Semolina model classes from warehouse views",
                    "url": "how-to/codegen",
                },
                {
                    "title": "How to configure codegen credentials",
                    "url": "how-to/codegen-credentials",
                },
                {
                    "title": "How to test query code without a warehouse",
                    "url": "how-to/warehouse-testing",
                },
                {"title": "How to use Semolina in a web API", "url": "how-to/web-api"},
            ],
        },
        {
            "title": "Reference",
            "url": "reference/index",
            "children": [
                {"title": "Configuration file reference", "url": "reference/config"},
                {"title": "CLI reference", "url": "reference/cli"},
                {"title": "semolina", "url": "reference/api/semolina/index"},
            ],
        },
        {
            "title": "Explanation",
            "url": "explanation/index",
            "children": [
                {"title": "What is a semantic view?", "url": "explanation/semantic-views"},
                {
                    "title": "Warehouse types and what lands in your row",
                    "url": "explanation/type-fidelity",
                },
                {
                    "title": "Developing on DuckDB, deploying elsewhere",
                    "url": "explanation/duckdb-vs-warehouse",
                },
            ],
        },
    ],
}
