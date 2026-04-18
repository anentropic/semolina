# Sphinx Shibuya Guidance

Opinionated preferences for writing documentation with Sphinx and the Shibuya theme. These are style preferences -- agents already understand RST and Sphinx syntax. This file guides how features should be used, not what they are.

## Admonitions

- Prefer admonition directives over bold text for callouts. Bold text in paragraphs gets lost; directives create visual hierarchy that readers scan.
- Use specific admonition types instead of generic `.. note::`:
  - `.. tip::` for best practices and recommended approaches
  - `.. warning::` for gotchas, common mistakes, and things that might surprise
  - `.. danger::` for breaking changes, security concerns, and data loss risks
  - `.. note::` for supplementary context that enriches understanding
  - `.. versionadded:: X.Y` for new features introduced in a specific release
  - `.. deprecated:: X.Y` for deprecation notices with migration guidance
- Do not stack multiple admonitions back-to-back. If you need three warnings in a row, consolidate into one admonition with a list.
- Example:

  ```rst
  .. tip::

     Use ``client.connect(timeout=30)`` for slow networks. The default
     timeout of 10 seconds is too aggressive for high-latency connections.
  ```

## Code Blocks

- Always use `.. code-block:: {language}` -- never use bare `::` for code that readers will copy. Bare `::` omits syntax highlighting and language context.
- Use `:emphasize-lines:` to highlight important lines in longer examples. Do not highlight everything -- highlight only the lines that are new or critical.
- Use `:caption:` to label file paths: `.. code-block:: python` with `:caption: src/main.py`. This tells readers where the code belongs.
- Use `:linenos:` only for long examples where line numbers aid discussion in surrounding text. Short snippets do not need line numbers.
- Prefer tab sets (sphinx-design) over consecutive code blocks when showing the same concept in multiple languages or installation methods.

## Tab Sets

- Use `.. tab-set::` with `.. tab-item::` directives from sphinx-design for multi-language or multi-method examples. Tabs keep alternatives side-by-side without page bloat.
- Use `:sync-group:` on the tab-set and `:sync:` on tab-items to synchronize related tabs across the page. When a reader selects Python in one tab set, all tab sets with the same sync group switch to Python.
- Keep tab labels short and consistent: "Python", "JavaScript", "pip", "conda" -- not "Python Example" or "Install via pip".
- Group related alternatives: install methods (pip/conda/docker), OS-specific instructions (macOS/Linux/Windows), sync/async patterns.
- Do not use tabs for unrelated content. If the tabs show different concepts rather than different expressions of the same concept, use separate sections instead.
- Example:

  ```rst
  .. tab-set::
     :sync-group: lang

     .. tab-item:: Python
        :sync: python

        .. code-block:: python

           client = MyClient(api_key="...")

     .. tab-item:: JavaScript
        :sync: js

        .. code-block:: javascript

           const client = new MyClient({ apiKey: "..." });
  ```

## sphinx-design Components

sphinx-design provides grids, cards, dropdowns, badges, and buttons as RST directives. Use them proactively where they improve clarity or navigation -- do not wait for the user to ask.

- **Grids and cards** (`.. grid::`, `.. grid-item-card::`): Use for landing pages, feature overviews, and section index pages. Grid responsiveness values `1 2 3 3` adapt from 1 column on mobile to 3 on desktop. Use `:link:` on cards for navigation so the entire card is clickable.
- **Dropdowns** (`.. dropdown::`): Use for optional or advanced content that most readers can skip. Equivalent to collapsible admonitions in other frameworks. Use `:color:` and `:icon:` for visual distinction between informational and warning dropdowns.
- **Badges** (`:bdg-success:`, `:bdg-warning:`, `:bdg-info:`): Use inline for version markers (`v2.1`), stability status (`stable`, `beta`), and deprecation notices. Keep badge text short -- one or two words.
- **Buttons** (`.. button-ref::`): Use on landing pages for prominent calls-to-action (e.g., "Get Started" pointing to the quickstart tutorial). Do not overuse -- one or two buttons per page maximum.
- Be proactive about suggesting sphinx-design features where they improve clarity or navigation. Suggest grids for landing pages, tabs for multi-language code, dropdowns for advanced content.
- Reference: full component inventory at https://sphinx-design.readthedocs.io/en/latest/

## Navigation

### Three Navigation Strategies

The setup Q&A offers three strategies. The guidance below documents how each renders in Sphinx/Shibuya so the doc-author writes the correct structure.

- The front page must appear as "Overview" in the nav at the same level as the section tabs — use "Overview" rather than "Home", as it signals that the page orients the reader to the project structure.
- For sidebar-only nav (no nav_links), ensure the root index.rst is labelled "Overview" as the first sidebar entry, at the same level as the section headings.

#### Strategy 1: Sections as Top Tabs

Each diataxis section (Tutorials, How-To Guides, Explanation, Reference) becomes a dropdown tab in the top navbar via `nav_links` in conf.py. Each dropdown shows children with summaries.

- `nav_links` are configured in `html_theme_options` in conf.py. They are static URL lists -- they do NOT derive from the toctree and have no build-time validation.
- Each section has its own `index.rst` with a `:hidden:` toctree listing its child pages.
- The root `index.rst` has a hidden toctree listing all section index files.
- When a reader clicks a tab, the sidebar shows only that section's toctree (scoped sidebar).
- nav_links URLs are plain strings (e.g., `"tutorials/index"`), NOT RST cross-references. Do NOT use `:ref:` or `:doc:` syntax in nav_links.

### Left Nav Depth

- Keep left nav to 3 levels maximum (section heading -> page -> sub-page). Deeper nesting creates narrow, scrolling nav panels that frustrate readers.
- Level 1: section heading (e.g., "Authentication"). Level 2: page (e.g., "OAuth Setup"). Level 3: sub-page as a child entry. Avoid Level 4.
- Use `index.rst` files for section landing pages. Each section landing page should have a toctree listing the section's pages with `:maxdepth: 2`.
- Root `index.rst` should use a hidden toctree (`:hidden:`) listing all Diataxis section indexes so the sidebar populates without rendering a visible list on the landing page.

### Section Index Pages with Abstracts

Section index pages (e.g., `tutorials/index.rst`) serve as landing pages for each documentation section. They list child pages with a 1-sentence abstract beneath each link.

- Each child page should have `.. meta:: :description: One-sentence abstract` at the top. This provides machine-readable metadata for HTML meta tags and social sharing.
- The section index page writes abstracts INLINE beneath each link -- readers see the abstracts directly on the index page, not pulled from metadata automatically.

## Page Metadata

- RST pages do not use YAML frontmatter. Use field lists at the top of a page for metadata, or `:orphan:` to exclude a page from toctree warnings.
- Use page titles (RST heading underlines) as the canonical title. Do not duplicate the title in metadata fields.

## Cross-References

- Use `:ref:\`label\`` for ALL internal links. Place labels (`.. _label-name:`) above headings. Labels survive page moves and restructuring; file-path references do not.
- STRONGLY DISCOURAGE `:doc:\`path\`` for internal navigation. It couples links to file paths. When pages move, every `:doc:` reference breaks. Use `:ref:` with descriptive labels instead.
- Use intersphinx roles for external Sphinx project links: `:py:class:\`pathlib.Path\``, `:py:func:\`os.path.join\``.
- Inline code mentions of project APIs should use domain roles: `:py:func:\`my_func\``, `:py:class:\`MyClass\``, `:py:meth:\`MyClass.method\``.

## sphinx-autoapi Integration

- autoapi output REPLACES the Reference tab entirely. The Author agent MUST NOT write manual reference pages when autoapi is enabled. Docstrings are the source of truth -- manual pages drift out of sync.
- Google docstring style is the convention. All docstrings should follow Google style with Parameters, Returns, Raises, and Example sections.
- Set `autoapi_python_class_content = "both"` to show both class-level and `__init__` docstrings.
- Include `sphinx.ext.napoleon` in conf.py extensions alongside `autoapi.extension`.
