# `fabricatio-typst`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-typst)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-typst)](https://pypi.org/project/fabricatio-typst/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-typst/week)](https://pepy.tech/projects/fabricatio-typst)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-typst)](https://pepy.tech/projects/fabricatio-typst)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

Academic article generation and Typst document tooling, built on Fabricatio's event-based agent framework.

## Installation

```bash
pip install fabricatio[typst]
```

For RAG-backed article writing:

```bash
pip install fabricatio[typst,rag]
```

## Overview

Two layers compose this package:

**Rust extension** (`fabricatio_typst.rust`) — performance-critical utilities:
- TeX-to-Typst math conversion (raw LaTeX and delimited `$`/`$$`/`\(`/`\[` math)
- BibTeX bibliography management with fuzzy citation lookup
- Typst comment manipulation and YAML front-matter handling
- Markdown section extraction

**Python layer** — agent-based academic content generation:
- Extract paper essences and generate structured research proposals
- Build hierarchical article outlines and generate full content
- RAG-backed article writing with citation-aware iterative retrieval
- Store and query article chunks in LanceDB

## Rust API

```python
from fabricatio_typst.rust import (
    BibManager,
    tex_to_typst,
    convert_all_tex_math,
    comment,
    uncomment,
    strip_comment,
    split_out_metadata,
    to_metadata,
    extract_body,
    replace_thesis_body,
    extract_sections,
    fix_misplaced_labels,
)
```

### TeX Conversion

| Function | Description |
|---|---|
| `tex_to_typst(string)` | Convert raw LaTeX code to Typst math |
| `convert_all_tex_math(string)` | Convert `$`, `$$`, `\(`, `\[` math delimiters to Typst `$` |

```python
tex_to_typst(r"\frac{1}{\sqrt{x^2 + 1}}")
# => '#frac(1, sqrt(x^2 + 1))'

convert_all_tex_math("Einstein's $E = mc^2$ is famous.")
# => "Einstein's $E = m c^2$ is famous."
```

### Comment Utilities

| Function | Description |
|---|---|
| `comment(string)` | Prepend `//` to every line |
| `uncomment(string)` | Remove `//` prefix from every line |
| `strip_comment(string)` | Strip leading and trailing comment lines |

### BibManager

Loads a BibTeX bibliography file and provides fuzzy citation lookup.

```python
bib = BibManager("references.bib")
cite_key = bib.get_cite_key_by_title("Attention Is All You Need")
# => "vaswani2017attention"

key = bib.get_cite_key_fuzzy("transformers attention mechanism")
authors = bib.get_author_by_key(key)
abstract = bib.get_abstract_by_key(key)
```

| Method | Description |
|---|---|
| `get_cite_key_by_title(title)` | Exact-match citation key by title |
| `get_cite_key_by_title_fuzzy(title)` | Fuzzy-match citation key by title |
| `get_cite_key_fuzzy(query)` | Fuzzy-match citation key by arbitrary query |
| `list_titles(is_verbatim=False)` | List all bibliography titles |
| `get_author_by_key(key)` | Authors for a citation key |
| `get_year_by_key(key)` | Publication year for a citation key |
| `get_abstract_by_key(key)` | Abstract for a citation key |
| `get_title_by_key(key)` | Title for a citation key |
| `get_field_by_key(key, field)` | Arbitrary BibTeX field for a citation key |

### Document Utilities

| Function | Description |
|---|---|
| `split_out_metadata(string)` | Extract YAML front matter as `(metadata, rest)` |
| `to_metadata(data)` | Serialize Python object to YAML comment block |
| `extract_body(string, wrapper)` | Extract content between wrapper markers |
| `replace_thesis_body(string, wrapper, new_body)` | Replace content between wrapper markers |
| `extract_sections(string, level=1, section_char="#")` | Parse markdown sections at given header level |
| `fix_misplaced_labels(string)` | Move `\<label\>` tags outside display math blocks |

## Python Models

Hierarchical article representation from proposal through completed paper:

| Model | Description |
|---|---|
| `ArticleProposal` | Research proposal: problems, approaches, methods, aims, keywords |
| `ArticleEssence` | Semantic fingerprint: title, authors, equations, figures, contributions |
| `ArticleOutline` | Hierarchical outline: chapters → sections → subsections |
| `ArticleChapterOutline` | Chapter-level outline node |
| `ArticleSectionOutline` | Section-level outline node |
| `ArticleSubsectionOutline` | Subsection-level outline node |
| `Article` | Complete paper with full content and validation |
| `ArticleChapter` | Chapter with sections |
| `ArticleSection` | Section with subsections |
| `ArticleSubsection` | Subsection with paragraphs |
| `Paragraph` | Structured paragraph blueprint with word count |
| `ArticleChunk` | LanceDB-storable chunk with bibtex metadata |
| `ArticleEssenceStorable` | ArticleEssence with LanceDB storage capability |
| `CitationManager` | Deduplicated, iteratively expanded citation set for RAG |
| `ChunkKwargs` | TypedDict for chunking parameters |

## Actions

Each action is a Fabricatio `Action` — an async callable unit in the agent workflow. Available actions:

### Content Extraction

| Action | Description |
|---|---|
| `ExtractArticleEssence` | Extract article essences from files on disk |
| `FixArticleEssence` | Fix extracted essences using BibTeX reference data |
| `ExtractOutlineFromRaw` | Parse an outline from raw text |

### Generation

| Action | Description |
|---|---|
| `GenerateArticleProposal` | Generate a research proposal from a briefing |
| `GenerateInitialOutline` | Build an outline from a proposal |
| `GenerateArticle` | Generate full article content from an outline |
| `LoadArticle` | Load a complete article from outline + Typst code |
| `WriteChapterSummary` | Write summaries for each chapter |
| `WriteResearchContentSummary` | Write a research content summary |

### RAG-Backed Writing

| Action | Description |
|---|---|
| `WriteArticleContentRAG` | Write article content with citation-aware RAG |
| `ArticleConsultRAG` | Retrieve relevant citations for article sections |
| `TweakArticleLancedbRAG` | Refine article content using LanceDB RAG |
| `ChunkArticle` | Split an article into storeable chunks |
| `StoreArticleEssence` | Store article essences into LanceDB |

### Citation Capability

`CitationLancedbRAG` — citation-aware iterative search that expands queries over multiple rounds and deduplicates by bibtex key.

## Workflows

Pre-composed action pipelines:

| Workflow | Steps |
|---|---|
| `WriteOutlineCorrectedWorkFlow` | `GenerateArticleProposal` → `GenerateInitialOutline` → dump output |
| `StoreArticle` | `ExtractArticleEssence` → `StoreArticleEssence` |

Usage:

```python
from fabricatio_typst.actions.article import GenerateArticleProposal, GenerateInitialOutline
from fabricatio_typst.models.article_proposal import ArticleProposal
from fabricatio_typst.models.article_outline import ArticleOutline

async def generate_outline():
    proposal: ArticleProposal = await GenerateArticleProposal()._execute(
        article_briefing="Quantum error correction in near-term devices"
    )
    print(f"Proposal: {proposal.title}")

    outline: ArticleOutline = await GenerateInitialOutline()._execute(
        article_proposal=proposal
    )
    print(f"Outline chapters: {len(outline.chapters)}")
```

## Dependencies

- `fabricatio-core` — agent framework and core models
- `fabricatio-tool` — filesystem utilities
- `fabricatio-capabilities` — capability mixins (Extract, Censor, etc.)

Optional for article generation workflows:

- `fabricatio-actions` — output dumping actions
- `fabricatio-improve`, `fabricatio-rule` — content improvement and validation

Optional for RAG features:

- `fabricatio-lancedb` — vector storage and retrieval

## CLI

The package includes the `ttm` (TeX to Typst Math) binary:

```bash
# Convert math in a file
ttm file input.md -o output.md

# Convert raw LaTeX string
ttm raw "\frac{a}{b}"

# Convert a string with math delimiters
ttm string "The formula $\int_0^\infty e^{-x} dx$ is useful."
```

## Configuration

`TypstConfig` exposes tunable settings via the Fabricatio config system:

```python
from fabricatio_typst.config import typst_config

typst_config.paragraph_sep         # "// - - -"
typst_config.article_wrapper       # "// =-=-=-=-=-=-=-=-=-="
typst_config.chap_summary_template # "built-in/chap_summary"
```

## License

MIT — see [LICENSE](../../LICENSE)
