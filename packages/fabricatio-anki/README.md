# `fabricatio-anki`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-anki)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-anki)](https://pypi.org/project/fabricatio-anki/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-anki/week)](https://pepy.tech/projects/fabricatio-anki)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-anki)](https://pepy.tech/projects/fabricatio-anki)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

AI-powered Anki flashcard deck generation and compilation for the Fabricatio framework. Uses LLM-driven templates to produce card layouts, model definitions, and topic analyses, then compiles them into `.apkg` files compatible with Anki 2.1+.

## Installation

```bash
pip install fabricatio[anki]
# or
uv pip install fabricatio[anki]
```

For the full Fabricatio suite:

```bash
pip install fabricatio[full]
```

## Overview

The package splits into two layers:

- **Rust** (`fabricatio_anki.rust`) — fast filesystem operations for project scaffolding, template serialization, and deck compilation via `deck_loader`.
- **Python** (`fabricatio_anki`) — LLM-driven generation of deck metadata, card models, HTML/JS/CSS templates, and topic analyses, integrated with Fabricatio's `Propose` capability system.

## Project Structure

A deck project created by `create_deck_project` follows this layout:

```
deck_project/
├── deck.yaml           # Deck metadata (name, description, author)
├── models/             # One subdirectory per note type
│   └── basic_card/
│       ├── fields.yaml # Field definitions (e.g. Front, Back)
│       └── templates/  # One subdirectory per card template
│           └── card/
│               ├── front.html
│               ├── back.html
│               └── style.css
├── data/               # CSV files with card content
│   └── basic_card.csv
└── media/              # Global images, audio, etc.
```

## Rust Functions (`fabricatio_anki.rust`)

| Function | Description |
|---|---|
| `compile_deck(path, output)` | Compile a deck project into an `.apkg` file. |
| `create_deck_project(path, deck_name?, description?, author?, model_name?, fields?)` | Scaffold a new deck project with sample templates and data. |
| `save_metadata(dir_path, name, data)` | Write a Python dict as YAML into a project directory. |
| `add_csv_data(project_path, model_name, data_path)` | Copy a CSV file into the project's `data/` directory. |
| `save_template(dir_path, front, back, css?)` | Write `front.html`, `back.html`, and optional `style.css` for a card template. |
| `extract_html_component(html)` | Parse an HTML string into `(layout, js, css)` by separating `<script>` and `<style>` content. |
| `extract_content_by_tag(html, tag)` | Extract inner text from all occurrences of a given HTML tag. |

## Python Models

| Model | Description |
|---|---|
| `Template` | Card template with `front` and `back` `Side` objects (each containing `layout`, `js`, `css`). |
| `Side` | One face of a card — HTML layout, JavaScript, and CSS. |
| `Model` | Note type with a name, field list, and list of `Template`s. |
| `Deck` | Full deck with metadata, author, and list of `Model`s. |
| `ModelMetaData` | Patch class carrying deck-level metadata (name, description, author). |
| `TopicAnalysis` | Analysis of a topic: difficulty coefficient, subjects, detailed solution, key points, summary. |

## Python Capabilities

### `GenerateDeck`

LLM-driven deck generation. Extends `Propose`. Key methods:

| Method | Description |
|---|---|
| `generate_deck(requirement, fields, …)` | Generate a complete `Deck` from a natural-language requirement. |
| `generate_model(fields, requirement, …)` | Generate `Model`(s) with auto-named templates. |
| `generate_template(fields, requirement, …)` | Generate `Template`(s) with front/back HTML, JS, and CSS. |
| `generate_front_side(fields, requirement, …)` | Generate front-side `Side` objects. |
| `generate_back_side(fields, requirement, …)` | Generate back-side `Side` objects. |

Accepts a single `requirement` string or a list for batch generation. All methods pass through Fabricatio's validation system.

### `GenerateAnalysis`

Generates structured `TopicAnalysis` objects from topic strings.

| Method | Description |
|---|---|
| `generate_analysis(topic, …)` | Produce `TopicAnalysis` for one or more topics. |

### `AppendTopicAnalysis`

An `Action` that reads a CSV file, runs `generate_analysis` on each row, and appends a "Topic Analysis" column.

```python
from fabricatio_anki.actions.topic_analysis import AppendTopicAnalysis

action = AppendTopicAnalysis(
    csv_file="questions.csv",
    output_file="questions_with_analysis.csv",
)
result = await action.execute()
```

## Configuration

`AnkiConfig` (loaded from Fabricatio's config system under the `anki` key) controls which templates are used during generation. Each field names a `built-in/…` template in the template manager. Override via configuration to swap in custom generation prompts.

## Usage Example

```python
from fabricatio_anki.rust import create_deck_project, compile_deck, add_csv_data
from pathlib import Path

# 1. Scaffold a project
create_deck_project(
    Path("./my_deck"),
    deck_name="French Vocabulary",
    description="Essential French words for beginners",
    author="Language Team",
    model_name="french_vocab",
    fields=["French", "English", "Pronunciation", "Example"],
)

# 2. Add your CSV data
add_csv_data(Path("./my_deck"), "french_vocab", Path("./words.csv"))

# 3. Compile to .apkg
compile_deck(Path("./my_deck"), Path("./french_vocab.apkg"))
```

For LLM-driven generation via `GenerateDeck`:

```python
from fabricatio_anki.capabilities.generate_deck import GenerateDeck

gen = GenerateDeck()
deck = await gen.generate_deck(
    "Create a deck for learning Japanese JLPT N5 vocabulary",
    fields=["Kanji", "Reading", "Meaning", "Example Sentence"],
)
# deck is a Deck with auto-generated models and templates
```

## Dependencies

- `fabricatio-core` — core interfaces and utilities
- `fabricatio-capabilities` — capability framework (Propose)
- `deck_loader` (Rust) — Anki deck serialization and project management

## License

MIT — see [LICENSE](LICENSE)
