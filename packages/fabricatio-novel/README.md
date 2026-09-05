# `fabricatio-novel`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-novel)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-novel)](https://pypi.org/project/fabricatio-novel/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-novel/week)](https://pepy.tech/projects/fabricatio-novel)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-novel)](https://pepy.tech/projects/fabricatio-novel)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

AI-powered novel generation — outline to publication-ready EPUB.

> Full dataflow and generation-logic walkthrough:
> [docs/superpowers/specs/2026-08-21-novel-generation-dataflow.md](../../docs/superpowers/specs/2026-08-21-novel-generation-dataflow.md)

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

Generation runs a staged, template-driven pipeline over a context tree
(`NovelContext → ChapterContext → StoryContext → SceneContext`), with every plan and
character state proposed by the LLM in batched calls:

1. **Metadata** — outline → `NovelPlan` (title, description, word count, global writing
   constraint, bible)
2. **Characters** — bible roster → one `CharacterSpan` (start + end card) per character
   for the whole novel
3. **Chapters** — chapter plans, then **N-1 boundary cards** per character so chapter 1
   starts at the roster start and the last chapter ends at the roster end
4. **Stories** — per chapter: story plans, then **S-1 boundary cards** per character
   anchored on the chapter's start/end
5. **Scenes** — per story: scene plans; the story's spans are broadcast to every scene,
   which is where the prose is actually written
6. **Assembly** — the composed context tree becomes a `Novel`; `NovelBuilder`
   (Rust/PyO3) produces the EPUB
7. **Illustration** (`wri` only) — one post-process pass proposes an image prompt per
   scene, renders it via ComfyUI, and embeds the PNGs in the EPUB

Character state is **two pure cards, never an interpolated chain**: the LLM is only
asked for the coarsest boundary states, and code stitches them so continuity is
guaranteed. Single-child levels inherit their parent's spans with no LLM call.

The CLI runs the pipeline as a **staged workflow** (`DebugNovelWorkflow`), persisting a
whole-tree JSON snapshot after every stage so any wrong result is traceable:

```
01_init → 02_metadata → 03_characters → 04_chapter_plans → 05_story_plans
       → 06_scene_plans → 07_scenes → 08_novel → 09_export
```

An optional RAG variant (`RagDebugNovelWorkflow`) retrieves `WritingStyleDocument`
entries from LanceDB once per story and renders them raw into the scene prompts.

The `wri` variant (`RagIllustrationDebugNovelWorkflow`) appends one final post-process
stage that illustrates every scene of the finished context before export; its stage
snapshots stay identical to `wr`'s.

## Data Flow & Prompt Assembly

The pipeline follows one principle: **every LLM touchpoint is a template plus named
context variables, and nothing else**. Each stage renders a Handlebars template from the
current context channel; planner calls parse the reply into validated pydantic models,
while the single prose call captures raw paragraphs. Everything between calls — word-count
allocation, character-arc stitching, prefix propagation, assembly — is deterministic code.

<p align="center"><img src="./assets/pipeline.svg" alt="Staged pipeline with its LLM call inventory" width="790"></p>

### LLM call inventory

| Stage | Template · prompted with | Yields |
|---|---|---|
| Metadata | `novel_metadata_requirement` ← `outline`, `language`, `constraint` | `NovelPlan` (adopted onto the root) |
| Roster spans | `novel_character_span` ← bible prompt block, title, description | `CharacterSpan[]` — skipped without a roster |
| Chapter plans | `chapter_plan` ← outline, novel fields, word count, styles, constraint, characters | `ChapterPlan[]` |
| Chapter boundaries | `chapter_character_span` ← roster spans, chapter titles/descriptions | N−1 boundary cards per character |
| Story plans | `story_plan` ← chapter fields, styles, constraint, characters, cast | `StoryPlan[]` |
| Story boundaries | `story_character_span` ← chapter spans, story titles/descriptions | S−1 boundary cards per character |
| Scene plans | `scene_plan` ← story fields, styles, constraint, characters, cast | `ScenePlan[]` |
| Scene prose | `scene_requirement` ← 11 variables, see below | plain prose → `Scene.content` |
| Scene illustration | `scene_illustration_prompt` ← novel/chapter/story/scene titles, description, content, cast, `illustration_constraint` | `SketchSpec` (prompt, negative prompt, LLM-chosen `mp`/`prop`) → PNGs rendered concurrently per scene (post-process) |

Templates live in `templates/built-in/` and are selectable through the
[Configuration](#configuration) keys below.

### What flows down the tree

Plans materialize into child contexts via `from_plan`; each level then passes state down:

- **Running manuscript** — an append-only `ContextLog`; every walk seeds each child with
  exactly the bytes that precede it in the final book (`iter_prefixed_contexts`)
- **Setting bible** — rendered once at the root into a `setting_bible` prefix entry;
  every descendant inherits it through its own log
- **Word budget** — each level splits its `expected_word_count` among children by plan weight
- **Writing constraint** — accumulated verbatim down the chain
- **Character arcs** — the roster fixes both endpoints; intermediate boundary cards are
  proposed per level and stitched in code; scenes receive the finished span list read-only

Composed prose flows back up: scene content enters the logs, and `Novel.from_context`
aggregates the whole tree for export.

<p align="center"><img src="./assets/dataflow.svg" alt="Context-tree data flow: what flows down, what flows up" width="820"></p>

### How a scene prompt is assembled

The scene write is the only content-producing call, so its prompt is engineered for
provider prefix caching: every row above `## Scene` is byte-identical across the scenes
of a story, and divergence starts exactly at the per-scene tail.

<p align="center"><img src="./assets/prompt-assembly.svg" alt="Scene prompt assembly: sources, template sections, response" width="760"></p>


## Key Classes

### Context channels

| Class | Role |
|---|---|
| `NovelContext` | Root channel: outline, language, roster `charactor_span`, `chapter_context` |
| `ChapterContext` | Chapter channel: `charactor_span`, `story_context`, heading block |
| `StoryContext` | Story channel: `charactor_span`, `scene_context`, accumulated `writing_styles`, optional `rag` retrieval settings |
| `SceneContext` | Leaf channel: broadcast `charactor_span`, `content` (the only composed prose) |
| `CharacterSpan` | Start + end `CharacterCard`; `derive_child_spans` stitches boundary cards |
| `ContextLog` / `ContextEntry` | Append-only manuscript log per channel: `append`, `branch` (fork history), `clear` (fresh fork); renders the prefixed-content prompt streams |
| `SeriesBible` | `characters` name list + `background_settings` fact list; rendered once into a `setting_bible` prefix entry at the root |

Every channel carries its running manuscript as an **append-only `ContextLog`**: composed
blocks enter as frozen `ContextEntry` records, parents seed children with pure log snapshots,
and prompts render them exactly like the former prefixed-content strings. Logs support
`with_entry`/`with_entries` appends, `branch()` to fork alternative continuations from any
point (copy-on-write), and `clear()` which returns a fresh empty log while the original
history stays intact.

### Plans & models

| Class | Description |
|---|---|
| `NovelPlan` | Novel metadata: title, description, word count, global constraint, bible |
| `ChapterPlan` / `StoryPlan` / `ScenePlan` | Weighted per-element plans (title, description, weight, style, constraint, cast) |
| `Scene` / `Story` / `Chapter` / `Novel` | Materialized output tree with word-count satisfaction |
| `SketchSpec` / `IllustratedScene` | LLM-proposed generation instruction — positive/negative prompt plus per-scene `mp`/`prop` (comfyui model); the scene output carrying its rendered illustration |
| `WritingStyleDocument` / `EnrichedDocument` | LanceDB-backed writing-style references |

### Capabilities (mixins)

| Class | Description |
|---|---|
| `SceneCompose` | Scene requirement rendering + prose generation |
| `StoryCompose` | Scene planning, scene write preparation, serial scene composition |
| `ChapterCompose` | Story planning, `draft_story_spans` (S-1 boundary cards), story composition |
| `NovelCompose` | Metadata, `prepare_character_span` (roster), chapter planning, `draft_chapter_spans` (N-1 boundary cards) |
| `RAGCompose` | Retrieves style docs once per story; extends scene prompts |
| `BibleCompose` | Creates/updates the setting bible from an outline |
| `IllustrateScenes` | Post-process illustration: batch-proposes one complete generation instruction (`SketchSpec`: prompt, negative prompt, LLM-chosen `mp`/`prop`) per pending scene (honoring `illustration_constraint`), renders them concurrently via ComfyUI into the run's `images/` directory, and attaches `IllustratedScene` outputs |

### Actions (staged workflow)

| Action | Stage |
|---|---|
| `InitNovelContext` | `01_init` — build context from outline/language/constraint/bible, then fire `before_compose_novel_context` |
| `ProposeNovelMetadataStage` | `02_metadata` — `propose_novel_metadata` |
| `PrepareCharacterSpanStage` | `03_characters` — `prepare_character_span` (roster) |
| `PlanChaptersStage` | `04_chapter_plans` — `plan_chapters_phase` + boundary drafting |
| `PlanStoriesStage` | `05_story_plans` — fires `before_compose_chapter_context` per chapter, then `plan_stories_phase` + boundary drafting |
| `PlanScenesStage` / `RagPlanScenesStage` | `06_scene_plans` — fires `before_compose_story_context` per story, then `plan_scenes_phase` (with RAG) |
| `ComposeScenesStage` / `RagComposeScenesStage` | `07_scenes` — writes scene prose, then closes each story (`after_compose_story_context` + `post_process_story`) and each chapter (`after_compose_chapter_context` + `post_process_chapter`) |
| `AssembleNovelStage` | `08_novel` — fires `after_compose_novel_context`, then `assemble_novel` |
| `IllustrateNovelStage` | `DumpNovelStage` whose `post_process_novel` resolves to per-scene illustration; adds no snapshot dir |
| `DumpNovelStage` | fires `post_process_novel`, then export — JSON always; EPUB and/or per-chapter `chapters/NN.txt` per `format` |

Every stage wraps one `compose_novel` chain segment and fires the chain's lifecycle hooks at their chain positions, so a hook override on a stage customizes the staged run exactly like it customizes the programmatic chain; the scene-level hooks fire inside `compose_scenes_phase`, exactly as they do in the chain.

### Workflows

| Workflow | Description |
|---|---|
| `DebugNovelWorkflow` | Outline → exported novel (`--format epub\|txt\|both`), one stage per action with per-stage snapshots |
| `RagDebugNovelWorkflow` | Same, with writing-style RAG per story |
| `RagIllustrationDebugNovelWorkflow` | Same, plus a single post-process pass that renders a ComfyUI illustration for every scene into the EPUB |

### Rust / PyO3

| Symbol | Description |
|---|---|
| `NovelBuilder` | Builder for EPUB 3.0 novels: title/description/authors, chapters (auto-XHTML), cover, fonts, CSS, TOC |
| `text_to_xhtml_paragraphs` | Plain text → `<p>`-wrapped XHTML paragraphs |

## Configuration

All options below are read through the fabricatio configuration chain (see the
[Configuration Guide](../../docs/source/configuration.rst)). Set them under the
`[ext.novel]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.novel]` in `pyproject.toml`, or via
`FABRICATIO_EXT__NOVEL__<FIELD_UPPER>` environment variables.

```toml
[ext.novel]
novel_metadata_requirement_template = "built-in/novel_metadata_requirement"
```

| Option | Type | Default | Description |
|---|---|---|---|
| `novel_metadata_requirement_template` | `str` | `"built-in/novel_metadata_requirement"` | template used to extract the novel metadata (title, synopsis, word count) from the outline. |
| `chapter_plan_template` | `str` | `"built-in/chapter_plan"` | template used to plan the chapters of the novel from the outline and metadata. |
| `story_plan_template` | `str` | `"built-in/story_plan"` | template used to plan the stories of a chapter. |
| `scene_plan_template` | `str` | `"built-in/scene_plan"` | template used to plan the scenes of a story. |
| `scene_requirement_template` | `str` | `"built-in/scene_requirement"` | template used to write a single scene in full prose. |
| `render_chapter_xhtml_template` | `str` | `"built-in/render_chapter_xhtml"` | template used to render a chapter as a full XHTML document. |
| `scene_overlap_min_chars` | `int` | `40` | minimum whitespace-normalized overlap between a new scene's prefix and the previous prose that gets stripped; shorter echoes are kept. |
| `scene_overlap_max_ratio` | `float` | `0.6` | maximum fraction of a generated scene the overlap may cover before the content is kept untouched with a warning instead of stripped. |
| `setting_bible_characters_template` | `str` | `"built-in/setting_bible_characters"` | template used to propose the bible's character roster as a list of plain strings, one character per item. |
| `setting_bible_background_template` | `str` | `"built-in/setting_bible_background"` | template used to propose the bible's background settings as a list of strings. |
| `setting_bible_context_template` | `str` | `"built-in/setting_bible_context"` | template that renders the bible into the block seeded into the running manuscript prefix. |
| `setting_bible_export_template` | `str` | `"built-in/setting_bible_export"` | template used to render the bible as a human-readable markdown document. |
| `writing_style_as_prompt_template` | `str` | `"built-in/writing_style_as_prompt"` | template used to render writing style documents as prompts. |
| `enriched_as_prompt_template` | `str` | `"built-in/enriched_as_prompt"` | template used to render enriched reference documents as prompts. |
| `novel_character_span_template` | `str` | `"built-in/novel_character_span"` | template used to propose the novel roster as one CharacterSpan per character. |
| `chapter_character_span_template` | `str` | `"built-in/chapter_character_span"` | template used to draft the N-1 chapter-boundary cards from the novel roster spans. |
| `story_character_span_template` | `str` | `"built-in/story_character_span"` | template used to draft the S-1 story-boundary cards from the chapter's spans. |
| `scene_illustration_prompt_template` | `str` | `"built-in/scene_illustration_prompt"` | template used to propose one image-generation prompt for a composed scene. |
| `illustration_constraint` | `str` | `""` | global style/content constraint merged into every scene illustration prompt proposal; empty when unset. |
| `illustration_negative_prompt` | `str` | quality/anatomy exclusion list | negative prompt forwarded to ComfyUI for every scene illustration unless the proposal supplies its own. |
| `illustration_mp` | `float \| None` | `None` | megapixel budget of each scene illustration's finished image (1.0 = 1,000,000 px); a per-scene proposal's `mp` wins, otherwise `None` falls back to `[ext.comfyui] mp`, then the active ComfyUI template's canvas. |
| `illustration_mp_max` | `float` | `1.2` | hard ceiling on every scene illustration's megapixel budget, enforced at render time even when the LLM proposes a larger `mp`; the renderable quality brink (512x512x2.2x2.2) is ~1.27 MP, so 1.2 keeps a margin under it. |
| `illustration_prop` | `str \| None` | `None` | aspect ratio of each scene illustration — `"16:9"` style values or `prop_16_9` names (e.g. `prop_2_3` for a portrait scene); a per-scene proposal's `prop` wins, otherwise `None` falls back to `[ext.comfyui] prop`, then the active ComfyUI template's ratio. |
| `illustration_seed` | `int \| None` | `None` | scene illustration sampler seed; `None` keeps the bundled ComfyUI template's seed. |
| `illustration_skip_existing` | `bool` | `True` | skip scenes whose illustration PNG already exists so re-runs fill only the gaps. |
| `illustration_timeout_per_image` | `float` | `210.0` | per-image render timeout in seconds; the total render timeout scales linearly with the batch size (value x pending renders) since all renders share one ComfyUI queue; `0` falls back to `[ext.comfyui] timeout`. |

Access at runtime: `from fabricatio_novel.config import novel_config`.

## Usage

### CLI

```bash
# Generate a novel from an outline
fanvl w -o "In a world where dreams are currency..."

# Generate with writing style RAG (LanceDB)
fanvl wr -o "In a world where dreams are currency..." -rq "Hemingway terse prose style"

# Generate with RAG + ComfyUI scene illustrations embedded in the EPUB
fanvl wri -o "In a world where dreams are currency..." -rq "Hemingway terse prose style"

# Constrain generation with a setting bible + global writing constraint
fanvl w -o "..." -b settings/bible.json -c "first person view throughout"

# Export as plain text instead of (or besides) EPUB: chapters/01.txt, 02.txt, …
fanvl w -o "..." --format both
fanvl w -o "..." --format txt

# Create / update / show the setting bible
fanvl bible create -o "In a world where dreams are currency..." --out settings/bible.json
fanvl bible update settings/bible.json -o "..." --sections characters
fanvl bible show settings/bible.json

# Store reference texts as writing style documents in LanceDB
fanvl store-refs ./corpus/*.txt
fanvl enrich-refs ./corpus/*.txt -eg "Extract world-building facts"
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
- `fabricatio-character` — Character card models
- `pydantic` — Data validation via models
- Optional: `fabricatio-lancedb` — writing style RAG, `typer` — CLI

## License

MIT — see [LICENSE](../../LICENSE)
