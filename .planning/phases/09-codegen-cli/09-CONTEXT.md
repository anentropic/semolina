# Phase 9: Codegen CLI - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a CLI tool that generates warehouse-native SQL (CREATE SEMANTIC VIEW for Snowflake, metric view definitions for Databricks) from Cubano Python model definitions. Users invoke the tool with model file paths and specify a target backend; the tool generates syntactically valid SQL formatted for readability, including field-level documentation from docstrings.

</domain>

<decisions>
## Implementation Decisions

### Input Handling
- Support flexible input: explicit file paths, directory scanning, and glob patterns (mix of all three)
- Generate all models in a file by default (no filtering needed at input stage)
- Silently skip files that don't contain Cubano models (e.g., utility modules in model directory)
- Fail immediately with clear error message if a user-specified path doesn't exist or can't be read

### Output Format & Structure
- Generated SQL pretty-printed (multi-line, indented) for human readability, not compact
- Include both model-level and field-level docstrings as SQL comments by default
- Use --no-comments flag to strip docstring comments if needed
- One output file per input file (models from `src/models.py` → `src/models.sql`)
- Trust template correctness; no SQL syntax validation before writing files

### CLI Command Interface
- Positional argument for input (file path, directory, or pattern): `cubano codegen <input>`
- Output to stdout by default, with errors and non-SQL information to stderr
  - Allows piping SQL directly to files or other tools if needed
- Named flags for options:
  - `--backend snowflake|databricks` (required; user specifies target, no default)
  - `--output <path>` (optional; default stdout if not specified)
- Short flags for convenience:
  - `-o` for `--output`
  - `-b` for `--backend`
- Standard CLI features:
  - `--version` — show Cubano version
  - `--help` — usage information
  - `--verbose` / `-v` — verbose logging for debugging codegen behavior

### Error Handling & Feedback
- Comprehensive error reporting: collect all errors during parsing and report together (not fail-fast)
  - Users see all issues at once, not one per fix cycle
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

</decisions>

<specifics>
## Specific Ideas

- Unix philosophy: CLI should compose well with pipes and scripts (stdout/stderr separation enables this)
- Error messages should feel like familiar tools (think `py_compile`, `mypy` style — helpful, not cryptic)
- CLI should be scriptable (no interactive prompts; fail fast on bad input with exit codes)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 9 scope.

</deferred>

---

*Phase: 09-codegen-cli*
*Context gathered: 2026-02-17*
