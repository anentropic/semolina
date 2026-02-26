# Phase 9: Codegen CLI - Research

**Researched:** 2026-02-17
**Domain:** CLI development, SQL generation, Python introspection
**Confidence:** HIGH

## Summary

Phase 9 builds a CLI tool that generates warehouse-native SQL from Cubano Python model definitions. The standard stack uses Typer for CLI parsing (modern, type-hint based) and Jinja2 for SQL templating (battle-tested for DDL generation). Python's built-in `inspect` module handles model introspection, and `importlib.util` handles dynamic module loading from file paths. The architecture follows Unix philosophy: clean stdout/stderr separation enables piping and composition.

Key findings: Typer's CliRunner provides excellent testing support, Jinja2's whitespace control is critical for readable SQL, and Python 3.11+ ExceptionGroups provide native support for collecting multiple errors. The main risks are SQL injection (mitigated by not accepting user parameters, only generating static DDL) and dynamic import security (mitigated by explicit file path validation).

**Primary recommendation:** Use Typer 0.12+ with Rich for colored output, Jinja2 3.1+ for templates, standard library inspect/importlib for introspection. Structure CLI as `cubano codegen <input>` with required `--backend` flag, separating SQL output (stdout) from diagnostics (stderr).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Input Handling:**
- Support flexible input: explicit file paths, directory scanning, and glob patterns (mix of all three)
- Generate all models in a file by default (no filtering needed at input stage)
- Silently skip files that don't contain Cubano models (e.g., utility modules in model directory)
- Fail immediately with clear error message if a user-specified path doesn't exist or can't be read

**Output Format & Structure:**
- Generated SQL pretty-printed (multi-line, indented) for human readability, not compact
- Include both model-level and field-level docstrings as SQL comments by default
- Use --no-comments flag to strip docstring comments if needed
- One output file per input file (models from `src/models.py` → `src/models.sql`)
- Trust template correctness; no SQL syntax validation before writing files

**CLI Command Interface:**
- Positional argument for input (file path, directory, or pattern): `cubano codegen <input>`
- Output to stdout by default, with errors and non-SQL information to stderr
- Named flags for options:
  - `--backend snowflake|databricks` (required; user specifies target, no default)
  - `--output <path>` (optional; default stdout if not specified)
- Short flags for convenience: `-o` for `--output`, `-b` for `--backend`
- Standard CLI features: `--version`, `--help`, `--verbose`/`-v`

**Error Handling & Feedback:**
- Comprehensive error reporting: collect all errors during parsing and report together (not fail-fast)
- Detailed error messages include file, line number, what's wrong, and how to fix
- Circular relationship validation: assume Cubano model API prevents invalid circular dependencies at model definition time; codegen doesn't need to re-validate this
- Success feedback to stderr with tasteful color and CLI flair (progress indicators, confirmation messages)
- SQL output to stdout remains clean (unpolluted by progress messages)

### Claude's Discretion

- Exact colors and styling for CLI output (tasteful, not garish)
- Progress bar design or text-based indicators
- Exact wording of error messages and help text
- How to determine what's a "non-SQL" message vs SQL output (stdout vs stderr routing details)
- Whether to implement model filtering (e.g., `--models Metric,Dimension` to select specific models within a file)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 9 scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CODEGEN-01 | User can run `cubano codegen` CLI to generate SQL from Cubano model files | Typer CLI framework with entry point configuration in pyproject.toml |
| CODEGEN-02 | Codegen generates CREATE SEMANTIC VIEW SQL (Snowflake syntax with AGG wrapping) | Snowflake official docs show CREATE SEMANTIC VIEW clause order (TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS); AGG() function wraps metrics in SELECT |
| CODEGEN-03 | Codegen generates metric view definitions for Databricks (MEASURE syntax) | Databricks MEASURE function for metric views; measures defined as aggregate expressions; YAML or SQL format |
| CODEGEN-04 | Codegen processes all models in a file, outputting multiple CREATE statements | inspect.getmembers() + inspect.isclass() to find SemanticView subclasses in module |
| CODEGEN-05 | Generated code passes syntax validation (`py_compile`, import checks) before writing | CONTEXT.md explicitly says "Trust template correctness; no SQL syntax validation before writing files" — this requirement conflicts with locked decision |
| CODEGEN-06 | Codegen validates no circular relationships in generated SQL | CONTEXT.md: "Circular relationship validation: assume Cubano model API prevents invalid circular dependencies at model definition time; codegen doesn't need to re-validate this" |
| CODEGEN-07 | User specifies output file and target backend (`--output path`, `--backend snowflake\|databricks\|both`) | Typer argument/option parsing; locked decision specifies single backend (not "both") |
| CODEGEN-08 | Generated SQL is formatted for readability and includes field comments from model docstrings | Jinja2 templates with whitespace control ({%- ... -%}); COMMENT ON COLUMN for Snowflake; inline -- comments for readability |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Typer | 0.12+ | CLI argument parsing, command routing | Modern Python CLI standard; type-hint based, auto-generates help, built on Click with testing utilities |
| Jinja2 | 3.1+ | SQL template generation | Industry standard for DDL generation; whitespace control, custom filters, used by dbt and major tools |
| Rich | 13.0+ | Terminal colors, progress indicators | De facto standard for beautiful CLI output; integrates seamlessly with Typer |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| importlib.util | stdlib | Dynamic module loading from file paths | Loading user's model files by absolute path (spec_from_file_location) |
| inspect | stdlib | Python introspection, class extraction | Finding SemanticView subclasses in loaded modules (getmembers, isclass) |
| pathlib | stdlib | File path handling, glob pattern expansion | Input validation, directory traversal, glob pattern support |
| ast | stdlib | Python syntax validation (if needed) | Note: CODEGEN-05 conflicts with CONTEXT.md; likely not needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Typer | argparse | argparse is stdlib but verbose; Typer provides modern type-hint interface |
| Typer | Click | Click is Typer's foundation; Typer adds type hints on top; use Typer for modern Python |
| Jinja2 | f-strings/templates | f-strings lack whitespace control and filter ecosystem; Jinja2 battle-tested for SQL |
| Rich | colorama/termcolor | Rich provides progress bars, tables, markdown rendering beyond basic colors |

**Installation:**

```bash
# Add to pyproject.toml dependencies
uv add typer>=0.12.0 jinja2>=3.1.0 rich>=13.0.0

# Or for development only
uv add --dev typer>=0.12.0 jinja2>=3.1.0 rich>=13.0.0
```

## Architecture Patterns

### Recommended Project Structure

```
src/cubano/
├── cli/                     # CLI command implementations
│   ├── __init__.py         # Typer app instance
│   ├── codegen.py          # codegen command implementation
│   └── utils.py            # CLI helpers (progress, error formatting)
├── codegen/                 # Codegen logic (separate from CLI)
│   ├── __init__.py
│   ├── loader.py           # Module loading, introspection
│   ├── generator.py        # SQL generation orchestration
│   ├── templates/          # Jinja2 templates
│   │   ├── snowflake.sql.jinja2
│   │   └── databricks.sql.jinja2
│   └── validators.py       # Error collection, validation
└── __main__.py             # Entry point for `python -m cubano`
```

### Pattern 1: Clean stdout/stderr Separation

**What:** Route SQL output to stdout, diagnostics/errors/progress to stderr
**When to use:** All CLI tools that produce parseable output (enables piping)

**Example:**

```python
# Source: https://thelinuxcode.com/how-to-print-to-stdout-and-stderr-in-python-with-real-cli-patterns-and-tests/
import sys
from rich.console import Console

# Create separate consoles for output vs diagnostics
stdout_console = Console(file=sys.stdout, stderr=False)  # SQL goes here
stderr_console = Console(file=sys.stderr, stderr=True)   # Progress/errors go here

# Usage
stderr_console.print("[green]Processing models...[/green]")  # Diagnostic
stdout_console.print(generated_sql)  # Clean SQL output
```

### Pattern 2: Dynamic Module Loading with importlib

**What:** Load Python modules from arbitrary file paths
**When to use:** User provides file path to their model definitions

**Example:**

```python
# Source: https://docs.python.org/3/library/importlib.html
import importlib.util
import sys
from pathlib import Path

def load_module_from_path(file_path: Path, module_name: str):
    """Load a Python module from an absolute file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # Cache in sys.modules
    spec.loader.exec_module(module)    # Execute module code
    return module
```

### Pattern 3: Introspect SemanticView Subclasses

**What:** Extract all SemanticView subclasses from a loaded module
**When to use:** After loading user's model file, find all model definitions

**Example:**

```python
# Source: https://docs.python.org/3/library/inspect.html
import inspect
from cubano import SemanticView

def find_semantic_views(module):
    """Find all SemanticView subclasses in a module."""
    views = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        # Check if it's a subclass of SemanticView but not SemanticView itself
        if issubclass(obj, SemanticView) and obj is not SemanticView:
            views.append(obj)
    return views
```

### Pattern 4: Error Collection with ExceptionGroup (Python 3.11+)

**What:** Collect multiple validation errors, report together
**When to use:** Processing multiple files/models; want comprehensive feedback

**Example:**

```python
# Source: https://peps.python.org/pep-0654/
errors = []

for file_path in input_files:
    try:
        process_file(file_path)
    except Exception as e:
        errors.append(e)

if errors:
    raise ExceptionGroup("Codegen failed with multiple errors", errors)
```

### Pattern 5: Jinja2 Template with Whitespace Control

**What:** Generate readable SQL with consistent indentation
**When to use:** All SQL template generation

**Example:**

```jinja2
{# Source: https://jinja.palletsprojects.com/en/stable/templates/ #}
{# Use {%- to strip left whitespace, -%} to strip right #}
CREATE OR REPLACE SEMANTIC VIEW {{ view_name }}
{%- if docstring %}
  -- {{ docstring }}
{%- endif %}
  DIMENSIONS (
  {%- for field in dimensions %}
    {{ field.name }}  -- {{ field.docstring if field.docstring else '' }}
    {%- if not loop.last %},{% endif %}
  {%- endfor %}
  )
  METRICS (
  {%- for field in metrics %}
    {{ field.name }}  -- {{ field.docstring if field.docstring else '' }}
    {%- if not loop.last %},{% endif %}
  {%- endfor %}
  );
```

### Pattern 6: Typer CLI with Required Enum Option

**What:** Enforce backend selection with Typer's enum support
**When to use:** Backend flag must be one of specific values

**Example:**

```python
# Source: https://typer.tiangolo.com/tutorial/commands/arguments/
from enum import Enum
import typer

class Backend(str, Enum):
    snowflake = "snowflake"
    databricks = "databricks"

app = typer.Typer()

@app.command()
def codegen(
    input_path: str = typer.Argument(..., help="Path to model file, directory, or glob pattern"),
    backend: Backend = typer.Option(..., "--backend", "-b", help="Target warehouse backend"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output file path (default: stdout)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Generate warehouse-native SQL from Cubano model definitions."""
    pass
```

### Anti-Patterns to Avoid

- **Using f-strings for SQL generation:** Loses whitespace control, no SQL injection protection, hard to maintain multi-line templates
- **Fail-fast on first error:** User has to fix one error at a time; collect and report all errors together
- **Progress messages to stdout:** Pollutes SQL output, breaks piping; always route diagnostics to stderr
- **Importing user modules without sys.modules caching:** Can cause duplicate imports and subtle bugs; use importlib.util properly
- **Hardcoded template strings in Python code:** Makes SQL hard to read/maintain; use separate .jinja2 files in templates/ directory

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | Manual sys.argv parsing | Typer | Type validation, help generation, subcommands, testing utilities built-in |
| SQL template generation | String concatenation/f-strings | Jinja2 | Whitespace control, filters, template inheritance, SQL-safe escaping |
| Terminal colors/progress | ANSI escape codes | Rich | Cross-platform, beautiful tables/trees/progress bars, markdown rendering |
| Module introspection | Manual __dict__ traversal | inspect module | Handles edge cases (metaclasses, descriptors), official Python API |
| File pattern matching | Manual glob logic | pathlib.Path.glob() | Recursive patterns (rglob), case-sensitivity control, generator-based (memory efficient) |
| Multiple error collection | Custom error list | ExceptionGroup (Python 3.11+) | Native language feature, proper traceback handling, except* syntax |

**Key insight:** CLI tooling has mature, battle-tested solutions. The complexity is in edge cases: cross-platform terminal support, proper error grouping, SQL injection prevention, Unicode handling. Use standard libraries.

## Common Pitfalls

### Pitfall 1: stdout/stderr Pollution

**What goes wrong:** Mixing SQL output and progress messages on stdout breaks piping
**Why it happens:** Default print() goes to stdout; developers add "Processing..." messages
**How to avoid:** Create separate Rich Console instances for stdout vs stderr; route all diagnostics to stderr

**Warning signs:**
- `cubano codegen models.py > output.sql` produces invalid SQL with progress messages
- Users can't pipe SQL directly to warehouse CLI tools

**Example fix:**

```python
# BAD: Everything to stdout
print("Processing models...")  # Pollutes SQL output
print(sql)

# GOOD: Separate streams
stderr_console.print("Processing models...")  # Diagnostic
stdout_console.print(sql)  # Clean SQL
```

### Pitfall 2: Dynamic Import Security Risks

**What goes wrong:** Loading arbitrary Python files can execute malicious code
**Why it happens:** importlib.util.exec_module() runs all module-level code
**How to avoid:** Validate file paths exist and are readable before import; document that codegen executes user code (same as `python models.py`)

**Warning signs:**
- No path validation before importing
- Importing from user-provided URLs or untrusted sources

**Mitigation:**
- Explicit path validation (file exists, readable, .py extension)
- Document security model: codegen runs user's Python code
- Don't support importing from URLs or stdin

### Pitfall 3: Jinja2 Whitespace Explosion

**What goes wrong:** Generated SQL has inconsistent indentation, extra blank lines
**Why it happens:** Jinja2 control structures add newlines; forgetting `{%-` and `-%}` markers
**How to avoid:** Use whitespace control markers consistently; test generated SQL formatting

**Warning signs:**
- Generated SQL has 2-3 blank lines between clauses
- Indentation varies randomly
- Trailing whitespace on lines

**Example fix:**

```jinja2
{# BAD: Whitespace explosion #}
{% for field in dimensions %}
  {{ field.name }}
{% endfor %}

{# GOOD: Controlled whitespace #}
{%- for field in dimensions %}
  {{ field.name }}
{%- endfor %}
```

### Pitfall 4: Missing Model Metadata

**What goes wrong:** Fields lack docstrings, model has no view name
**Why it happens:** User forgot to add docstrings; introspection doesn't fail gracefully
**How to avoid:** Check for required metadata; provide helpful error messages

**Warning signs:**
- Generated SQL has empty `-- ` comments
- Template assumes docstrings exist without checking

**Example fix:**

```python
# BAD: Assumes docstring exists
comment = field.__doc__

# GOOD: Graceful fallback
comment = inspect.getdoc(field) or ""
```

### Pitfall 5: Path Globbing Pitfalls

**What goes wrong:** Glob patterns match unexpected files, or fail silently
**Why it happens:** Glob patterns differ from shell globs; case sensitivity varies by platform
**How to avoid:** Use pathlib.Path.glob() with explicit case_sensitive parameter; validate pattern matches at least one file

**Warning signs:**
- User provides `src/**/*.py` but only top-level files are matched
- Pattern matches `.pyc` files or `__pycache__` directories

**Example fix:**

```python
# BAD: Assumes Unix shell behavior
import glob
files = glob.glob(pattern)  # Platform-dependent case sensitivity

# GOOD: Explicit pathlib usage
from pathlib import Path
files = list(Path(".").rglob(pattern))  # Consistent recursive glob
if not files:
    raise ValueError(f"Pattern '{pattern}' matched no files")
```

### Pitfall 6: Typer Testing Confusion

**What goes wrong:** Tests spawn subprocesses or fail to capture output
**Why it happens:** Not using CliRunner; calling Typer app directly
**How to avoid:** Use `typer.testing.CliRunner` in tests; check result.exit_code and result.output

**Warning signs:**
- Tests use `subprocess.run(["cubano", "codegen", ...])`
- Tests print output instead of asserting on result

**Example fix:**

```python
# BAD: Subprocess testing
import subprocess
result = subprocess.run(["cubano", "codegen", "models.py"], capture_output=True)

# GOOD: CliRunner testing
from typer.testing import CliRunner
runner = CliRunner()
result = runner.invoke(app, ["codegen", "models.py", "--backend", "snowflake"])
assert result.exit_code == 0
assert "CREATE SEMANTIC VIEW" in result.output
```

## Backend-Specific SQL Syntax

### Snowflake CREATE SEMANTIC VIEW

**Syntax structure:**

```sql
CREATE OR REPLACE SEMANTIC VIEW <view_name>
  TABLES (
    <table_ref> [AS <alias>]
  )
  RELATIONSHIPS (
    <relationship_def>
  )
  FACTS (
    <fact_field_name> = <expression>
  )
  DIMENSIONS (
    <dimension_field_name> = <expression>
  )
  METRICS (
    <metric_field_name> = <aggregate_expression>
  );
```

**Key constraints (source: [Snowflake CREATE SEMANTIC VIEW docs](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view)):**

- Clause order is strict: TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS
- Must define at least one DIMENSION or METRIC
- Metrics require AGG() function when queried: `SELECT AGG(revenue) FROM view`
- Metrics cannot appear in GROUP BY clause

**Field comments:**

```sql
-- Inline comments in generated SQL (for readability, not stored metadata)
METRICS (
  revenue = SUM(amount)  -- Total revenue from sales
)

-- Persistent column comments (separate statement)
COMMENT ON COLUMN view_name.revenue IS 'Total revenue from sales';
```

Source: [Snowflake COMMENT docs](https://docs.snowflake.com/en/sql-reference/sql/comment)

### Databricks Metric Views

**YAML syntax (primary format):**

```yaml
# Source: https://docs.databricks.com/aws/en/metric-views/data-modeling/syntax
metric_view_name:
  base_table: schema.table_name
  dimensions:
    - dimension_name:
        expr: column_expr
        description: "Dimension description"
  measures:
    - measure_name:
        expr: SUM(column)
        description: "Measure description"
```

**MEASURE function in queries:**

Unlike regular aggregates, MEASURE() doesn't specify aggregation type—it inherits from the metric view definition.

```sql
-- Query with MEASURE function
SELECT country, MEASURE(revenue)
FROM metric_view
GROUP BY country;
```

**Key differences from Snowflake:**

| Feature | Snowflake | Databricks |
|---------|-----------|------------|
| Definition format | SQL (CREATE SEMANTIC VIEW) | YAML or SQL |
| Query function | AGG(metric) | MEASURE(metric) |
| Comments | COMMENT ON COLUMN | description field in YAML |
| Aggregation location | In metric definition | In measure definition |

Source: [Databricks metric views docs](https://docs.databricks.com/aws/en/metric-views/)

## Code Examples

### Example 1: Complete Codegen Flow

```python
# Source: Combining patterns from official docs
from pathlib import Path
import importlib.util
import inspect
from jinja2 import Environment, FileSystemLoader
from cubano import SemanticView

def generate_sql(input_path: Path, backend: str) -> str:
    """Generate SQL from a Python model file."""

    # 1. Load module dynamically
    spec = importlib.util.spec_from_file_location("user_models", input_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {input_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 2. Find SemanticView subclasses
    views = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, SemanticView) and obj is not SemanticView:
            views.append(obj)

    if not views:
        raise ValueError(f"No SemanticView models found in {input_path}")

    # 3. Extract metadata
    view_data = []
    for view_cls in views:
        data = {
            "view_name": view_cls._view_name,
            "docstring": inspect.getdoc(view_cls) or "",
            "dimensions": [],
            "metrics": [],
            "facts": []
        }

        for field_name, field_obj in view_cls._fields.items():
            field_info = {
                "name": field_name,
                "docstring": inspect.getdoc(field_obj) or ""
            }

            if isinstance(field_obj, Dimension):
                data["dimensions"].append(field_info)
            elif isinstance(field_obj, Metric):
                data["metrics"].append(field_info)
            elif isinstance(field_obj, Fact):
                data["facts"].append(field_info)

        view_data.append(data)

    # 4. Render template
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(f"{backend}.sql.jinja2")

    return template.render(views=view_data)
```

### Example 2: Typer CLI with Testing

```python
# Source: https://typer.tiangolo.com/tutorial/testing/
import typer
from enum import Enum
from pathlib import Path

class Backend(str, Enum):
    snowflake = "snowflake"
    databricks = "databricks"

app = typer.Typer()

@app.command()
def codegen(
    input: str = typer.Argument(..., help="Model file, directory, or glob pattern"),
    backend: Backend = typer.Option(..., "--backend", "-b"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Generate warehouse-native SQL from Cubano models."""
    if verbose:
        typer.echo(f"Processing {input} for {backend.value}", err=True)

    # Generate SQL...
    sql = generate_sql(Path(input), backend.value)

    if output:
        output.write_text(sql)
        typer.echo(f"✓ Generated {output}", err=True)
    else:
        typer.echo(sql)  # stdout

# Testing
from typer.testing import CliRunner

def test_codegen():
    runner = CliRunner()
    result = runner.invoke(app, ["codegen", "models.py", "--backend", "snowflake"])
    assert result.exit_code == 0
    assert "CREATE SEMANTIC VIEW" in result.output
```

### Example 3: Error Collection Pattern

```python
# Source: https://peps.python.org/pep-0654/
from pathlib import Path

def process_multiple_files(file_paths: list[Path], backend: str) -> None:
    """Process multiple files, collecting all errors."""
    errors = []

    for file_path in file_paths:
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"{file_path} does not exist")
            if not file_path.is_file():
                raise ValueError(f"{file_path} is not a file")

            sql = generate_sql(file_path, backend)
            # ... write output

        except Exception as e:
            # Collect error with context
            errors.append(
                ValueError(f"Failed to process {file_path}: {e}")
            )

    # Raise all errors together
    if errors:
        raise ExceptionGroup(
            f"Codegen failed for {len(errors)} file(s)",
            errors
        )
```

## Validation Approaches

### Requirement CODEGEN-05 Conflict

**REQUIREMENTS.md states:** "CODEGEN-05: Generated code passes syntax validation (`py_compile`, import checks) before writing"

**CONTEXT.md states:** "Trust template correctness; no SQL syntax validation before writing files"

**Resolution:** CONTEXT.md takes precedence (locked user decision). CODEGEN-05 likely intended Python model validation (input), not SQL validation (output).

### Input Validation (Python Models)

**What to validate:**
- File path exists and is readable
- File is valid Python syntax (ast.parse)
- Module imports successfully
- At least one SemanticView subclass exists

**How:**

```python
import ast

def validate_python_syntax(file_path: Path) -> None:
    """Validate Python file syntax before importing."""
    try:
        code = file_path.read_text()
        ast.parse(code, filename=str(file_path))
    except SyntaxError as e:
        raise ValueError(f"Invalid Python syntax in {file_path}: {e}")
```

### Output Validation (SQL)

**User decision:** Skip SQL syntax validation

**Rationale:** Templates are static and tested; SQL syntax validation requires warehouse-specific parsers (complex, error-prone); trust template correctness.

**Alternative:** Provide `--validate` flag (Claude's discretion) to optionally run SQL syntax checks using third-party SQL parsers (sqlparse, sqlfluff).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| argparse manual parsing | Typer type-hint based | 2020 (Typer released) | Reduced boilerplate, better type safety |
| Manual exception lists | ExceptionGroup | Python 3.11 (2022) | Native multi-error handling, except* syntax |
| Click without types | Typer (Click + types) | 2020 | Auto-validation, IDE completion |
| String templates | Jinja2 | Long-established | SQL injection protection, whitespace control |
| colorama for colors | Rich | ~2020 | Progress bars, tables, markdown rendering |
| glob module | pathlib.Path.glob() | Python 3.4+ | Object-oriented, more consistent API |

**Deprecated/outdated:**

- **imp module:** Removed in Python 3.12; use importlib.util instead
- **argparse for modern CLIs:** Still valid but verbose; Typer preferred for new projects
- **Manual ANSI codes:** Use Rich for cross-platform terminal formatting

## Risk Assessment & Mitigation

### Risk 1: Security (Dynamic Import)

**Risk:** Executing arbitrary user Python code
**Likelihood:** HIGH (inherent to codegen design)
**Impact:** MEDIUM (local execution, not remote)

**Mitigation:**
- Document that codegen executes user's Python code (same trust model as `python models.py`)
- Validate file paths are explicit (no arbitrary imports)
- Don't support loading from URLs, stdin, or remote sources
- Run in same Python environment as user's code (no privilege escalation)

### Risk 2: Template Injection

**Risk:** User docstrings contain Jinja2 template syntax
**Likelihood:** LOW (docstrings are literals, not evaluated)
**Impact:** LOW (would break SQL generation, not execute code)

**Mitigation:**
- Disable Jinja2 autoescape (SQL doesn't need HTML escaping)
- Treat docstrings as plain strings (don't render as templates)
- Test with special characters in docstrings

### Risk 3: Path Traversal

**Risk:** User provides path like `../../sensitive/file.py`
**Likelihood:** MEDIUM (CLI accepts arbitrary paths)
**Impact:** MEDIUM (local file access only, not remote)

**Mitigation:**
- Resolve paths to absolute before validation
- Check file exists and is readable
- Don't follow symlinks without explicit flag
- Document that codegen reads user-specified files (expected behavior)

### Risk 4: Backend Syntax Divergence

**Risk:** Snowflake/Databricks change semantic view syntax
**Likelihood:** MEDIUM (evolving features)
**Impact:** HIGH (generated SQL fails)

**Mitigation:**
- Version templates alongside warehouse backend versions
- Include backend version in generated SQL comments
- Test generated SQL against real warehouses in CI
- Provide --backend-version flag for future compatibility

### Risk 5: Unicode/Encoding Issues

**Risk:** Non-ASCII characters in docstrings or model names
**Likelihood:** MEDIUM (international users)
**Impact:** LOW (file write errors, but caught immediately)

**Mitigation:**
- Default to UTF-8 encoding for all file operations
- Test with non-ASCII docstrings
- Validate Python identifiers (model/field names must be ASCII)

## Open Questions

1. **CODEGEN-05 vs CONTEXT.md conflict:**
   - What we know: REQUIREMENTS.md says validate, CONTEXT.md says don't
   - What's unclear: Was CODEGEN-05 referring to input (Python) or output (SQL)?
   - Recommendation: Validate Python input syntax (ast.parse), skip SQL output validation per CONTEXT.md

2. **Databricks SQL vs YAML format:**
   - What we know: Databricks supports both SQL and YAML for metric views
   - What's unclear: Which format should codegen produce?
   - Recommendation: Use YAML (more common in docs, clearer structure for comments)

3. **Model filtering flag:**
   - What we know: CONTEXT.md lists as "Claude's discretion"
   - What's unclear: Does user need `--models Revenue,Cost` to select specific models from a file?
   - Recommendation: Defer to planning; likely not needed for v1 (generate all models by default)

4. **Progress indicators for large files:**
   - What we know: User wants "tasteful CLI flair"
   - What's unclear: When to show progress? Single file = no progress, directory = show progress?
   - Recommendation: Show progress bar when processing >5 files; spinner for long-running single file loads

## Sources

### Primary (HIGH confidence)

- [Typer Official Documentation](https://typer.tiangolo.com/) - CLI framework, testing, printing
- [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/en/stable/templates/) - Template syntax, whitespace control
- [Python inspect module documentation](https://docs.python.org/3/library/inspect.html) - Class introspection
- [Python importlib documentation](https://docs.python.org/3/library/importlib.html) - Dynamic module loading
- [Snowflake CREATE SEMANTIC VIEW docs](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view) - Snowflake SQL syntax
- [Databricks metric views docs](https://docs.databricks.com/aws/en/metric-views/) - Databricks MEASURE syntax
- [PEP 654 – Exception Groups](https://peps.python.org/pep-0654/) - Multi-error handling

### Secondary (MEDIUM confidence)

- [Building CLI Tools with Typer and Rich (2026)](https://dasroot.net/posts/2026/01/building-cli-tools-with-typer-and-rich/) - Typer + Rich integration
- [How to Print to stdout and stderr in Python – TheLinuxCode](https://thelinuxcode.com/how-to-print-to-stdout-and-stderr-in-python-with-real-cli-patterns-and-tests/) - stdout/stderr best practices
- [Jinja2 Tutorial - Whitespace control](https://ttl255.com/jinja2-tutorial-part-3-whitespace-control/) - SQL formatting
- [Comprehensive Testing of Snowflake's New SQL Syntax for Semantic Views (2026)](https://medium.com/@masato.takada/comprehensive-testing-of-snowflakes-new-sql-syntax-for-semantic-views-db4485d90556) - Recent Snowflake syntax verification
- [How To Test CLI Applications With Pytest, Argparse And Typer](https://pytest-with-eric.com/pytest-advanced/pytest-argparse-typer/) - Typer testing patterns

### Tertiary (LOW confidence)

None — all findings verified with official documentation.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - Typer, Jinja2, Rich are industry standards with stable APIs
- Architecture patterns: HIGH - All patterns drawn from official docs and established best practices
- Backend SQL syntax: HIGH - Verified with 2026 Snowflake/Databricks documentation
- Pitfalls: MEDIUM-HIGH - Based on documented issues and community experience
- Security risks: MEDIUM - Standard dynamic import risks, well-understood mitigations

**Research date:** 2026-02-17
**Valid until:** ~2026-04-17 (60 days; SQL syntax and CLI patterns are stable)

---

## RESEARCH COMPLETE

**Phase:** 09 - Codegen CLI
**Confidence:** HIGH

### Key Findings

1. **Typer + Rich is the modern Python CLI standard** — type-hint based, excellent testing support, beautiful output
2. **Jinja2 whitespace control is critical** — {%- -%} markers prevent whitespace explosion in generated SQL
3. **ExceptionGroup (Python 3.11+) provides native multi-error handling** — no need for custom error collection
4. **stdout/stderr separation is non-negotiable** — enables piping SQL to other tools
5. **CODEGEN-05 conflicts with CONTEXT.md** — recommend validating Python input, skip SQL output validation

### File Created

`.planning/phases/09-codegen-cli/09-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Typer, Jinja2, Rich are industry standards with 4+ years stability |
| Architecture | HIGH | All patterns from official Python/library docs |
| Backend Syntax | HIGH | Verified with 2026 Snowflake/Databricks official docs |
| Pitfalls | MEDIUM-HIGH | Based on documented issues and community patterns |
| Security | MEDIUM | Standard dynamic import risks, well-known mitigations |

### Open Questions

1. CODEGEN-05 interpretation: Input validation (Python) or output validation (SQL)? → Recommend input validation only
2. Databricks format preference: SQL or YAML? → Recommend YAML (clearer structure, better docs support)
3. Model filtering flag needed? → Defer to planning, likely not v1 requirement
4. Progress indicator thresholds? → Suggest >5 files for progress bar, spinner for slow single-file loads

### Ready for Planning

Research complete. Planner can now create PLAN.md files with:
- Typer CLI implementation tasks
- Jinja2 template creation tasks
- Module introspection logic
- Error collection and reporting
- Test coverage with CliRunner
