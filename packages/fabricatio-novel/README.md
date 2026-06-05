# `fabricatio-novel`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-novel)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-novel)](https://pypi.org/project/fabricatio-novel/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-novel/week)](https://pepy.tech/projects/fabricatio-novel)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-novel)](https://pepy.tech/projects/fabricatio-novel)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

AI-powered novel generation — outline to publication-ready EPUB.

## Installation

```bash
pip install fabricatio[novel]
# or
uv pip install fabricatio[novel]
```

For the CLI tool:

```bash
pip install fabricatio-novel[cli]
```

## Pipeline

Novel generation runs as a five-stage sequential pipeline driven by Handlebars templates.

1. **Draft** — Outline text → `NovelDraft` (title, genre, synopsis, chapter list, character descriptions, language detection)
2. **Characters** — `NovelDraft` → `CharacterCard[]` (one per described character)
3. **Scripts** — `NovelDraft` + `CharacterCard[]` → `Script[]` (batched; each script is a list of `Scene` objects with per-scene prompts and global writing guidance)
4. **Chapters** — `Script[]` + `CharacterCard[]` → raw chapter text (sequential; each chapter receives a rolling `ChapterSummary` from the previous chapter for narrative continuity)
5. **Assembly** — Components assembled into a `Novel` object; `NovelBuilder` (Rust/PyO3) produces the EPUB

An optional RAG variant (`NovelComposeRAG`) queries LanceDB for `WritingStyleDocument` entries and injects them into script-level `global_prompt` and scene-level `prompt` fields before chapter generation.

## Key Classes

### Models

| Class | Description |
|---|---|
| `NovelDraft` | High-level novel plan: title, genre, synopsis, character descriptions, ordered `ChapterDraft` list, expected word count |
| `ChapterDraft` | Per-chapter outline with title, detailed synopsis, and weight (for word-count allocation) |
| `Script` | Sequence of `Scene` objects with a `global_prompt` for chapter-level writing guidance |
| `Scene` | Basic narrative unit: narrative description, tone/style prompt, tags, weight |
| `ChapterSummary` | Structured summary of a generated chapter — key events, character states, emotional arc, unresolved threads |
| `ChapterPlan` | Bundles a `ChapterDraft`, its `Script`, and computed word count per chapter |
| `Chapter` | Final chapter with XHTML content, zero-based index, and word count |
| `Novel` | Collection of `Chapter` objects with aggregate word count and compliance ratio |
| `WritingStyleDocument` | LanceDB-backed document for storing and retrieving writing style references |
| `NovelConfig` | Frozen dataclass specifying built-in template names for all pipeline stages |

### Capabilities (Mixins)

| Class | Description |
|---|---|
| `NovelCompose` | Full pipeline: `create_draft`, `create_characters`, `create_scripts`, `create_chapters`, `summarize_chapter`, `assemble_novel`, `compose_novel` |
| `NovelComposeRAG` | Extends `NovelCompose` — fetches writing style docs from LanceDB and injects them into script/scene prompts before chapter generation |

### Actions (fabricatio-actions)

| Class | Description |
|---|---|
| `GenerateNovelDraft` | Generate a `NovelDraft` from an outline |
| `GenerateCharactersFromDraft` | Generate `CharacterCard` list from a draft |
| `GenerateScriptsFromDraftsAndCharacters` | Generate `Script` list from draft + characters |
| `GenerateChaptersFromScripts` | Generate chapter text sequentially from scripts + characters |
| `AssembleNovelFromComponents` | Build final `Novel` from draft, plans, and chapter contents |
| `ValidateNovel` | Validate chapter count, word count, and compliance ratio |
| `GenerateNovel` | Run the full pipeline in one action |
| `DumpNovel` | Serialize a `Novel` to disk as EPUB via `NovelBuilder` |

### Workflows (fabricatio-actions)

| Workflow | Description |
|---|---|
| `WriteNovelWorkflow` | One-step outline → EPUB |
| `DebugNovelWorkflow` | Step-by-step: draft → characters → scripts → chapters → validation → assembly → dump |
| `GenerateOnlyCharactersWorkflow` | Draft → characters only, for iterating on character design |
| `RewriteChaptersOnlyWorkflow` | Reuse existing scripts + characters to regenerate chapter prose |
| `ValidatedNovelWorkflow` | Full pipeline with quality gates (min chapters, word count, compliance ratio) |
| `RegenerateWithNewCharactersWorkflow` | A/B test character impact by re-running with fresh character generation |
| `DumpOnlyWorkflow` | Export a pre-built `Novel` object to EPUB |

### Rust / PyO3

| Symbol | Description |
|---|---|
| `NovelBuilder` | Builder for EPUB 3.0 novels: set title/description/authors, add chapters (auto-XHTML), cover images, fonts, CSS, inline TOC, export to file |
| `text_to_xhtml_paragraphs` | Convert plain text with newline-separated paragraphs to `<p>`-wrapped XHTML |

## Usage

### CLI

```bash
# Generate a novel from an outline
fanvl w "In a world where dreams are currency..."

# Generate with RAG writing style augmentation
fanvl wr "In a world where dreams are currency..."

# Store reference texts as writing style documents in LanceDB
fanvl store-refs ./corpus/*.txt
```

### Programmatic

```python
from fabricatio_novel.workflows.novel import DebugNovelWorkflow
from fabricatio_core import Event

event = Event.instantiate("write")
event.payload["novel_outline"] = "In a world where dreams are currency..."
role = Role.with_bio(name="writer").subscribe(event, DebugNovelWorkflow).dispatch()
```

### EPUB Builder (Rust)

```python
from fabricatio_novel.rust import NovelBuilder, text_to_xhtml_paragraphs

xhtml = text_to_xhtml_paragraphs(raw_chapter_text)

builder = (
    NovelBuilder()
    .new_novel()
    .set_title("My Novel")
    .add_author("Author Name")
    .add_chapter("Chapter 1", xhtml)
    .add_inline_toc()
)

builder.export("output.epub")
```

## Dependencies

- `fabricatio-core` — Core interfaces, template management, LLM capabilities
- `fabricatio-character` — Character generation and card models
- `pydantic` — Data validation via models
- Optional: `fabricatio-lancedb` — Writing style RAG, `fabricatio-actions` — workflow support, `questionary` + `typer` — CLI

## License

MIT — see [LICENSE](../../LICENSE)
