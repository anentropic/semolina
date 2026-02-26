# Phase 7: Packaging - Research

**Researched:** 2026-02-16
**Domain:** Python packaging, distribution, type information
**Confidence:** HIGH

## Summary

Python packaging in 2026 has consolidated around **pyproject.toml (PEP 621)** as the single source of truth for project metadata, dependencies, and build configuration. The cubano project is already well-configured with **uv-build** as the build backend, zero runtime dependencies, and optional extras for Snowflake and Databricks backends.

The primary packaging tasks are straightforward:

1. **Verify py.typed inclusion**: Already exists at `src/cubano/py.typed` and will be automatically included by uv-build
2. **Validate public API exposure**: `__all__` declarations already exist in `__init__.py` files
3. **Test installation scenarios**: Core library, individual extras, and combined extras
4. **Verify distribution contents**: Ensure wheels and source distributions contain expected files

The project follows modern best practices: zero dependencies for core library, lazy imports for optional backends (preventing ImportError when drivers aren't installed), and PEP 561 compliance for type checking support.

**Primary recommendation:** Use `uv build` to create distributions, verify contents with `unzip -l`, test installation with `pip install` in clean environments, and validate type information with basedpyright.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| uv-build | 0.9.18+ | Build backend | Official Astral build backend, 10-35x faster than alternatives, Rust-based portability |
| pyproject.toml | PEP 621 | Project metadata | Python packaging standard since 2020, single source of truth |
| py.typed | PEP 561 | Type information marker | Required for distributing inline type annotations |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| twine | latest | PyPI upload utility | When publishing to PyPI/TestPyPI |
| build | latest (fallback) | Build frontend | If uv-build has limitations, though unnecessary here |
| check-manifest | latest (optional) | MANIFEST validation | Legacy setuptools projects, not needed with uv-build |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| uv-build | hatchling | Hatchling supports extension modules (C/Rust), more mature ecosystem, but slower builds |
| uv-build | setuptools | Most compatible with legacy tooling, but significantly slower and complex configuration |
| pyproject.toml | setup.py | Legacy approach, no longer recommended for new projects |

**Installation:**
```bash
# Build dependencies are declared in pyproject.toml [build-system]
# No manual installation needed - build frontends fetch automatically

# For publishing (when ready):
uv pip install twine
```

## Architecture Patterns

### Recommended Project Structure
```
cubano/
├── pyproject.toml           # Single source of truth (metadata, deps, build config)
├── README.md                # Long description for PyPI
├── src/
│   └── cubano/
│       ├── __init__.py      # Public API with __all__
│       ├── py.typed         # PEP 561 marker (already exists)
│       ├── engines/
│       │   ├── __init__.py  # Engine exports with __all__
│       │   ├── snowflake.py # Lazy import: snowflake.connector
│       │   └── databricks.py # Lazy import: databricks.sdk
│       └── ...
└── tests/                   # Not included in distributions
```

### Pattern 1: Public API Exposure with `__all__`

**What:** Explicitly declare public API symbols in `__all__` lists at package boundaries
**When to use:** Every `__init__.py` that exposes a public API
**Example:**
```python
# Source: PEP 8, https://peps.python.org/pep-0008/
# Already implemented in src/cubano/__init__.py

from .fields import Dimension, Fact, Metric
from .query import Query
from .registry import register, get_engine, unregister

__all__ = [
    "Query",
    "Metric",
    "Dimension",
    "Fact",
    "register",
    "get_engine",
    "unregister",
]
```

**Benefits:**
- Controls `from cubano import *` behavior (though wildcard imports discouraged)
- Documentation tools use `__all__` to identify public API
- Clear contract: unlisted symbols are internal, subject to change
- Type checkers respect `__all__` for public API inference

### Pattern 2: Optional Dependencies with Lazy Imports

**What:** Import optional backend dependencies only when instantiated, not at module load time
**When to use:** For dependencies in `[project.optional-dependencies]` that users may not install
**Example:**
```python
# Source: Already implemented in src/cubano/engines/snowflake.py (Phase 05-01)

class SnowflakeEngine(Engine):
    def __init__(self, account: str, user: str, password: str, ...):
        # Store params, don't import yet
        self._account = account
        ...

    def execute(self, query: Query) -> list[Row]:
        # Lazy import: fails with ImportError only if user calls execute()
        # without installing cubano[snowflake]
        import snowflake.connector

        with snowflake.connector.connect(...) as conn:
            ...
```

**Benefits:**
- Users can `pip install cubano` without installing snowflake-connector-python
- ImportError occurs at use-time with clear context, not import-time
- Reduces installation size and dependency conflicts for users who only need Databricks

### Pattern 3: Version as Single Source of Truth

**What:** Store version in `pyproject.toml` only, let build backend propagate
**When to use:** Always, unless using dynamic versioning (e.g., setuptools_scm from git tags)
**Example:**
```toml
# Source: pyproject.toml (already implemented)

[project]
name = "cubano"
version = "0.1.0"  # Single source of truth
```

**Alternative approaches:**
- `version = {attr = "cubano.__version__"}` - reads from `__init__.py` (discouraged, multiple sources)
- `version = {file = "VERSION"}` - reads from file (unnecessary indirection)
- `dynamic = ["version"]` with setuptools_scm - reads from git tags (recommended for CI/CD automation)

**Current approach is simplest:** Static version in pyproject.toml, manually bump when releasing.

### Pattern 4: Type Information Distribution (PEP 561)

**What:** Include `py.typed` marker file to indicate package supports type checking
**When to use:** Libraries with inline type annotations (vs. separate stub packages)
**Example:**
```
src/cubano/
├── __init__.py
├── py.typed        # Empty file, signals "types available here"
├── query.py        # def execute(...) -> list[Row]:
└── ...
```

**Build backend handling (uv-build):**
- Automatically includes `py.typed` when co-located with Python modules
- No MANIFEST.in needed (uv-build uses declarative source-include patterns)
- Namespace packages require `py.typed` in submodules, not parent

**Verification:**
```bash
# After building, check wheel contains py.typed
unzip -l dist/cubano-0.1.0-py3-none-any.whl | grep py.typed
# Expected: cubano/py.typed
```

### Anti-Patterns to Avoid

- **Don't use `from cubano import *` in documentation examples:** List imports explicitly to show users the public API
- **Don't put version in multiple places:** Leads to desync, PEP 621 discourages it
- **Don't import optional backends at module level:** Breaks for users without those extras installed
- **Don't rely on setuptools-specific features:** uv-build is PEP 517-compliant but not setuptools-compatible (e.g., no setup.py hooks)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Build system | Custom setup.py scripts | uv-build (or hatchling) | PEP 517 compliance, reproducibility, build isolation, cross-platform portability |
| Dependency specification | requirements.txt for library | pyproject.toml [project.dependencies] | PEP 621 standard, version ranges, extras support, recognized by all modern tools |
| Type stub distribution | Separate -stubs package | Inline annotations + py.typed | Easier to maintain (no sync issues), better IDE experience, PEP 561 recommendation |
| Version management (simple) | __version__ in code | pyproject.toml static version | Single source of truth, no import-time dependencies |
| Version management (CI/CD) | Manual version bumping | setuptools_scm with git tags | Automated from VCS, prevents desync, no manual edits |

**Key insight:** The Python packaging ecosystem has matured significantly. Using modern declarative configuration (pyproject.toml) with standards-compliant build backends (uv-build) eliminates entire classes of problems that plagued setup.py-era packaging (platform-specific build issues, incorrect dependency resolution, missing files in distributions).

## Common Pitfalls

### Pitfall 1: py.typed Not Included in Distribution

**What goes wrong:** After adding `py.typed` to source tree, users installing package report "no type information available" in IDEs, type checkers fail to find types
**Why it happens:** With setuptools, `py.typed` requires explicit configuration via `package_data` or `include_package_data=True`; historically forgotten or misconfigured
**How to avoid (uv-build):** Co-locate `py.typed` with `__init__.py` in package directory; uv-build automatically includes it (verified by WebSearch finding that `uv init --lib` creates py.typed)
**How to avoid (hatchling fallback):** No special config needed if `py.typed` is in package directory
**Warning signs:** After `pip install`, type checker reports "library does not export type information" despite annotations in source
**Verification:**
```bash
# Build and inspect wheel
uv build
unzip -l dist/cubano-*.whl | grep py.typed

# Test installation in clean venv
uv venv test-env
source test-env/bin/activate
uv pip install dist/cubano-*.whl
python -c "import cubano; print(cubano.__file__)"  # Find install location
ls -la $(python -c "import cubano, pathlib; print(pathlib.Path(cubano.__file__).parent)")/py.typed
```

### Pitfall 2: Optional Dependencies Not Installed with Extras

**What goes wrong:** User runs `pip install cubano[snowflake]`, attempts to use SnowflakeEngine, still gets `ImportError: No module named 'snowflake.connector'`
**Why it happens:**
- Typo in extra name (e.g., `cubano[Snowflake]` vs. `cubano[snowflake]` - extras normalized to lowercase)
- Extra defined in pyproject.toml but not actually listing dependencies
- Cached wheel from before extras were added (pip cache not cleared)
**How to avoid:**
- Use exact extra names from `[project.optional-dependencies]` keys
- Verify extra dependencies listed: `uv pip show cubano --verbose` (shows extras)
- Clear pip cache after build: `uv cache clean`
**Warning signs:** ImportError mentions missing backend library despite installing with `[extra]`
**Verification:**
```bash
# Test each extra in isolated environment
uv venv test-snowflake
source test-snowflake/bin/activate
uv pip install ./dist/cubano-*.whl[snowflake]
python -c "import snowflake.connector; print('OK')"

# Verify extra is recognized
uv pip show cubano | grep "Optional dependencies"
```

### Pitfall 3: Editable Install Doesn't Reflect Changes

**What goes wrong:** Developer runs `pip install -e .`, makes code changes, but changes not reflected when importing (old behavior persists)
**Why it happens:**
- Some build backends create static redirector files (PEP 660 wheel-based editable installs)
- Changes to `__init__.py` or package structure may require reinstall
- Cached `.pyc` files from previous import
**How to avoid:**
- Use `uv pip install -e .` (uv's editable implementation is robust)
- For structural changes (new modules, renamed packages), reinstall: `uv pip install -e . --force-reinstall --no-deps`
- Clear `__pycache__`: `find . -name __pycache__ -exec rm -rf {} +` (if stuck)
**Warning signs:** Code changes visible in editor but not when running tests/scripts
**Verification:**
```bash
# Install editable with extras for development
uv pip install -e ".[snowflake,databricks]" --extra dev

# Verify editable mode (should show source path, not site-packages)
python -c "import cubano; print(cubano.__file__)"
# Expected: /Users/paul/Documents/Dev/Personal/cubano/src/cubano/__init__.py
```

### Pitfall 4: Forgetting to Test Core Installation (Zero Dependencies)

**What goes wrong:** Package works for developers (who have everything installed), fails for users doing minimal install
**Why it happens:**
- Developers test with `pip install -e ".[dev]"` which pulls in optional deps
- Accidental import of optional backend at module level (not lazily)
- Core library code accidentally depends on something in `[optional-dependencies]`
**How to avoid:**
- Always test: `pip install ./dist/cubano-*.whl` (no extras) in clean venv
- Try importing core API: `from cubano import Query, register, SemanticView`
- Verify zero deps: `pip show cubano` should list `Requires: ` (empty)
**Warning signs:** Users report ImportError for backend libraries despite not using those backends
**Verification:**
```bash
# Test minimal installation
uv venv test-core
source test-core/bin/activate
uv pip install ./dist/cubano-*.whl

# Should succeed (no backend dependencies)
python -c "from cubano import Query, Metric, Dimension, SemanticView, register"

# Should fail gracefully (backend not installed)
python -c "from cubano.engines import SnowflakeEngine; SnowflakeEngine(...).execute(...)"
# Expected: ImportError mentioning snowflake.connector when execute() called
```

### Pitfall 5: Wrong Module Name in pyproject.toml

**What goes wrong:** `uv build` succeeds, but wheel contains incorrect package structure (e.g., `my_lib/` instead of `my_lib-package/`)
**Why it happens:** With uv-build, package name defaults to normalized `project.name`; if source directory has different name, explicit `module-name` config needed
**How to avoid (cubano):** Not applicable - project name is "cubano", source directory is `src/cubano/`, names match
**How to avoid (generally):** If `project.name = "my-cool-lib"` but source is `src/my_cool_lib/`, add:
```toml
[tool.uv.build-backend]
module-name = "my_cool_lib"
```
**Warning signs:** After `pip install`, import fails: `ModuleNotFoundError: No module named 'cubano'`
**Verification:**
```bash
# Check wheel contains correct package
unzip -l dist/cubano-*.whl | grep "cubano/__init__.py"
# Expected: cubano/__init__.py (not cubano_package/__init__.py or other)
```

### Pitfall 6: RECORD File Mismatch (2026 PyPI Enforcement)

**What goes wrong:** Starting February 2026, PyPI rejects wheels where ZIP contents don't match RECORD metadata file
**Why it happens:** Manual wheel manipulation, build backend bugs, ZIP extraction/recompression with different tools
**How to avoid:** Use `uv build` directly, don't manually modify wheels, don't recompress with standard `zip` utility
**Warning signs:** PyPI upload fails with "RECORD file mismatch" error
**Verification:**
```bash
# twine check validates RECORD file
uv pip install twine
twine check dist/*

# Expected: "Checking dist/cubano-0.1.0-py3-none-any.whl: PASSED"
```

## Code Examples

Verified patterns from official sources:

### Testing Installation Scenarios

```bash
# Source: pip documentation (https://pip.pypa.io/en/stable/cli/pip_install/)

# 1. Build distributions
uv build
# Creates: dist/cubano-0.1.0-py3-none-any.whl
#          dist/cubano-0.1.0.tar.gz

# 2. Test core installation (zero dependencies)
uv venv /tmp/test-core && source /tmp/test-core/bin/activate
uv pip install dist/cubano-0.1.0-py3-none-any.whl
python -c "from cubano import Query, SemanticView; print('Core OK')"

# 3. Test Snowflake extra
uv venv /tmp/test-sf && source /tmp/test-sf/bin/activate
uv pip install "dist/cubano-0.1.0-py3-none-any.whl[snowflake]"
python -c "from cubano.engines import SnowflakeEngine; print('Snowflake OK')"

# 4. Test Databricks extra
uv venv /tmp/test-db && source /tmp/test-db/bin/activate
uv pip install "dist/cubano-0.1.0-py3-none-any.whl[databricks]"
python -c "from cubano.engines import DatabricksEngine; print('Databricks OK')"

# 5. Test combined extras
uv venv /tmp/test-all && source /tmp/test-all/bin/activate
uv pip install "dist/cubano-0.1.0-py3-none-any.whl[snowflake,databricks]"
python -c "from cubano.engines import SnowflakeEngine, DatabricksEngine; print('All OK')"
```

### Inspecting Distribution Contents

```bash
# Source: Standard Unix zipinfo utility

# List wheel contents
unzip -l dist/cubano-0.1.0-py3-none-any.whl

# Expected structure:
# cubano/__init__.py
# cubano/py.typed
# cubano/fields.py
# cubano/query.py
# cubano/engines/__init__.py
# cubano/engines/snowflake.py
# cubano/engines/databricks.py
# cubano-0.1.0.dist-info/METADATA
# cubano-0.1.0.dist-info/WHEEL
# cubano-0.1.0.dist-info/RECORD

# Verify py.typed is present
unzip -l dist/cubano-0.1.0-py3-none-any.whl | grep py.typed
# Expected: cubano/py.typed

# Check metadata (version, dependencies, extras)
unzip -p dist/cubano-0.1.0-py3-none-any.whl cubano-0.1.0.dist-info/METADATA

# Expected in METADATA:
# Name: cubano
# Version: 0.1.0
# Requires-Python: >=3.11
# Provides-Extra: databricks
# Provides-Extra: snowflake
# Requires-Dist: databricks-sql-connector[pyarrow]>=4.2.5; extra == "databricks"
# Requires-Dist: snowflake-connector-python>=4.3.0; extra == "snowflake"
```

### Verifying Type Information Distribution

```bash
# Source: PEP 561 (https://peps.python.org/pep-0561/)

# Install in test environment
uv venv /tmp/test-types && source /tmp/test-types/bin/activate
uv pip install dist/cubano-0.1.0-py3-none-any.whl

# Check py.typed is installed
python -c "import cubano, pathlib; print(pathlib.Path(cubano.__file__).parent / 'py.typed')"
ls -la $(python -c "import cubano, pathlib; print(pathlib.Path(cubano.__file__).parent)")/py.typed

# Run type checker against installed package
# (assumes basedpyright is available in environment or via uvx)
uv pip install basedpyright
basedpyright -c "from cubano import Query, SemanticView"
# Expected: No errors, type information resolved from installed package
```

### Development Workflow with Editable Install

```bash
# Source: PEP 660 (https://peps.python.org/pep-0660/)

# Install package in editable mode with all extras + dev tools
uv pip install -e ".[snowflake,databricks]" --extra dev

# Verify editable install points to source
python -c "import cubano; print(cubano.__file__)"
# Expected: /Users/paul/Documents/Dev/Personal/cubano/src/cubano/__init__.py

# Make changes to source code
# Changes immediately reflected without reinstall

# Run quality gates
uv run basedpyright   # Type checking
uv run ruff check     # Linting
uv run ruff format    # Formatting
uv run --extra dev pytest  # Tests

# Build and test distribution before committing
uv build
uv pip install --force-reinstall dist/cubano-*.whl
# Run tests again against installed wheel to catch packaging issues
```

### Publishing to PyPI (Future)

```bash
# Source: PyPI documentation (https://packaging.python.org/en/latest/guides/using-testpypi/)

# 1. Test on TestPyPI first (always)
uv pip install twine
twine check dist/*  # Validate metadata and RECORD

twine upload --repository testpypi dist/*
# Requires: Account on test.pypi.org, API token configured

# 2. Install from TestPyPI and verify
uv venv /tmp/test-pypi && source /tmp/test-pypi/bin/activate
uv pip install --index-url https://test.pypi.org/simple/ cubano
python -c "from cubano import Query; print('TestPyPI OK')"

# 3. After verification, upload to production PyPI
twine upload dist/*
# Requires: Account on pypi.org, API token configured
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| setup.py | pyproject.toml (PEP 621) | 2020 (PEP 621 accepted) | Declarative metadata, tool-agnostic, better version locking |
| requirements.txt for libraries | [project.dependencies] | 2020 (PEP 621) | Semantic versioning ranges, extras support, standardized format |
| MANIFEST.in | Build backend source-include patterns | 2021+ (PEP 517 backends mature) | Declarative in pyproject.toml, less error-prone |
| setup.py install | pip install | ~2020 (deprecated) | Build isolation, reproducibility, PEP 517 compliance |
| python setup.py sdist bdist_wheel | python -m build (or uv build) | 2021+ (PEP 517) | Build isolation in temporary venv, prevents local environment pollution |
| Separate stub packages (-stubs) | Inline annotations + py.typed | 2018+ (PEP 561, typing maturity) | Easier maintenance, no version desync, better IDE support |

**Deprecated/outdated:**
- `setup.py` for configuration - Still works but discouraged; use pyproject.toml (PEP 621)
- `python setup.py install` - Removed in setuptools 58.3.0+; use `pip install`
- `python setup.py sdist/bdist_wheel` - Use `python -m build` or `uv build` instead
- MANIFEST.in (with modern backends) - Use `[tool.uv.build-backend.source-include]` or equivalent
- `pkg_resources` for version introspection - Use `importlib.metadata.version()` (Python 3.8+)

## Open Questions

1. **Should version be static or dynamic (from git tags)?**
   - What we know: Current version is static `0.1.0` in pyproject.toml
   - What's unclear: If project will use git-based versioning (setuptools_scm, hatch-vcs) for automated releases
   - Recommendation: Keep static for 0.1.x releases; consider setuptools_scm after 1.0.0 if frequent releases

2. **Should package include a __version__ attribute?**
   - What we know: Not currently exposed in `__init__.py __all__`
   - What's unclear: Whether users expect `cubano.__version__` for runtime version checks
   - Recommendation: Add if requested by users; use `importlib.metadata.version("cubano")` pattern to avoid duplication

3. **TestPyPI upload before production PyPI?**
   - What we know: TestPyPI is best practice for first uploads
   - What's unclear: Whether user intends to publish to PyPI or keep package private
   - Recommendation: Defer until user requests public release; document TestPyPI workflow in PLAN

## Sources

### Primary (HIGH confidence)
- [PEP 621: pyproject.toml specification](https://packaging.python.org/en/latest/specifications/pyproject-toml/) - Project metadata standards
- [PEP 561: Distributing Type Information](https://peps.python.org/pep-0561/) - py.typed marker requirements
- [uv Build Backend Documentation](https://docs.astral.sh/uv/concepts/build-backend/) - uv-build capabilities and configuration
- [uv GitHub Issue #11502](https://github.com/astral-sh/uv/issues/11502) - Non-Python file inclusion (resolved 2025-03)
- Project files: pyproject.toml, src/cubano/__init__.py, src/cubano/py.typed

### Secondary (MEDIUM confidence)
- [Python Packaging User Guide: optional-dependencies](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) - WebSearch verified with official source
- [PEP 660: Editable Installs](https://peps.python.org/pep-0660/) - Editable install standardization
- [PEP 8: __all__ conventions](https://peps.python.org/pep-0008/) - Public API best practices
- [PyPI Blog: RECORD file validation](https://blog.pypi.org/posts/2025-08-07-wheel-archive-confusion-attacks/) - 2026 enforcement

### Tertiary (LOW confidence)
- [Medium: 2026 Golden Path for uv](https://medium.com/@diwasb54/the-2026-golden-path-building-and-publishing-python-packages-with-a-single-tool-uv-b19675e02670) - Community perspective on uv adoption
- [Hynek Schlawack: Recursive Optional Dependencies](https://hynek.me/articles/python-recursive-optional-dependencies/) - Advanced patterns not needed for cubano

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - uv-build, pyproject.toml, PEP 621, PEP 561 are official standards with mature documentation
- Architecture: HIGH - Patterns verified from official PEPs and cubano source code
- Pitfalls: MEDIUM-HIGH - Mix of official documentation (py.typed, extras) and practical experience (editable installs, testing)

**Research date:** 2026-02-16
**Valid until:** 90 days (stable domain, Python packaging changes slowly at standards level; tooling evolves faster but backward-compatible)
