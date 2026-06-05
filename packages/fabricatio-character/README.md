# `fabricatio-character`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-character)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-character)](https://pypi.org/project/fabricatio-character)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-character/week)](https://pepy.tech/projects/fabricatio-character)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-character)](https://pepy.tech/projects/fabricatio-character)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Character profile generation for the Fabricatio LLM agent framework — structured persona cards with AI-driven composition and template-based rendering.

---

## Installation

```bash
pip install fabricatio[character]
# or
uv pip install fabricatio[character]
```

For the full Fabricatio suite:

```bash
pip install fabricatio[full]
```

---

## Overview

`fabricatio-character` provides a `CharacterCard` model capturing a character's name, role, appearance, behavior, motivation, and flaw — six required fields that together define a complete narrative persona. The `CharacterCompose` capability plugs into Fabricatio's `Propose` pipeline to generate cards via LLM from natural-language requirements, with built-in Pydantic validation.

Generated cards are renderable through the Fabricatio template system (`as_prompt()`) and persistable (`PersistentAble`) for checkpoint/restore workflows.

---

## Models

### `CharacterCard`

A structured character profile. All six fields are required and non-empty.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Identifying name, alias, or title |
| `role` | `str` | Narrative or functional role within the story |
| `look` | `str` | Visual appearance — clothing, physique, distinguishing features |
| `act` | `str` | Typical behaviors, mannerisms, speech patterns, stress reactions |
| `want` | `str` | Core motivation or deepest goal driving the character's actions |
| `flaw` | `str` | Critical weakness, moral failing, or psychological vulnerability |

`CharacterCard` inherits:
- `SketchedAble` — instantiation from natural-language descriptions via LLM
- `Named` — equality by `name` field
- `AsPrompt` — renders as a prompt string via the configured template (`render_character_card_template`)
- `PersistentAble` — save/load to disk for workflow checkpointing

---

## Capabilities

### `CharacterCompose`

Mixin that extends `Propose` to generate `CharacterCard` instances from requirement strings.

```python
from fabricatio_character.capabilities.character import CharacterCompose

class StoryAgent(CharacterCompose, ...):
    pass
```

**`compose_characters(requirements, **kwargs)`**

- Accepts a single `str` or a `list[str]` of requirements
- Returns a single `CharacterCard` (or `None`) for a string, or a `list[CharacterCard | None]` for multiple requirements
- Passes `**kwargs` through to Fabricatio's validation layer (`ValidateKwargs`), enabling strict validation, retry policies, and custom post-processing
- Delegates to `Propose.propose()` for LLM-driven composition

---

## Utilities

### `dump_card(*card: CharacterCard) -> str`

Joins one or more `CharacterCard` objects as prompt strings, separated by newlines. Convenience wrapper around `CharacterCard.as_prompt()`.

```python
from fabricatio_character.utils import dump_card

prompt = dump_card(hero, villain)
```

---

## Configuration

| Setting | Default | Description |
|---|---|---|
| `render_character_card_template` | `"built-in/render_character_card"` | Template name used when rendering a card as a prompt |

Access via `fabricatio_character.config.character_config`, loaded through Fabricatio's `CONFIG` system.

---

## Dependencies

- `fabricatio-core` — `Propose`, `SketchedAble`, `Named`, `CONFIG`
- `fabricatio-capabilities` — `AsPrompt`, `PersistentAble`, `ValidateKwargs`

---

## Usage

### Generating a Single Character

```python
from fabricatio_character.capabilities.character import CharacterCompose

class Agent(CharacterCompose, ...):
    pass

agent = Agent()
card = await agent.compose_characters(
    "a grizzled detective haunted by an old case"
)
if card:
    print(card.as_prompt())
```

### Batch Generation with Validation

```python
cards = await agent.compose_characters(
    [
        "a brilliant but arrogant surgeon",
        "a quiet archivist who notices everything",
        "a cheerful smuggler with a heart of gold",
    ]
)
for c in cards:
    print(c.name, "-", c.role)
```

### Rendering and Persistence

```python
from fabricatio_character.utils import dump_card

# Render all cards as prompts
prompt_text = dump_card(*cards)

# Persist individual cards (via PersistentAble)
card.persist("checkpoints/characters/")
```

---

## License

MIT — see [LICENSE](LICENSE)
