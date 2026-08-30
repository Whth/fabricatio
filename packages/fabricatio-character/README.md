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

`fabricatio-character` provides a `CharacterCard` model capturing a character as they currently are: stable identity (name, roles list, activated role, motivation) plus the mutable state of the moment (appearance, behavior, vulnerability, location, physical condition, mood) — ten required fields that together define a complete narrative persona and its present situation, plus an optional `metric` map of tracked numerical stats (hp, energy, reputation, ...). The `CharacterCompose` capability plugs into Fabricatio's `Propose` pipeline to generate cards via LLM from natural-language requirements, with built-in Pydantic validation.

Generated cards are renderable through the Fabricatio template system (`as_prompt()`) and persistable (`PersistentAble`) for checkpoint/restore workflows.

---

## Models

### `CharacterCard`

A character as they currently are. The identity fields (`name`, `roles`, `activated_role`, `want`) change slowly; the state fields describe how the character is right now and evolve as the story progresses. The ten text fields are required and non-empty; `metric` is optional. `roles` must contain at least one entry and `activated_role` must be one of the entries in `roles`.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Identifying name, alias, or title |
| `roles` | `list[str]` | All narrative or functional roles the character holds within the story (e.g. `["protagonist", "mentor"]`); non-empty |
| `activated_role` | `str` | The role the character is currently playing; must be one of the entries in `roles` |
| `look` | `str` | Current appearance — clothing, physique, distinguishing features, wounds, disguise |
| `act` | `str` | Current behaviors, mannerisms, stress reactions |
| `want` | `str` | Core motivation driving the character's actions (slow-changing) |
| `flaw` | `str` | Current weakness, moral failing, or psychological vulnerability |
| `where` | `str` | Current location and immediate situation |
| `condition` | `str` | Current physical state — health, energy, injuries, resources |
| `mood` | `str` | Current emotional state |
| `metric` | `dict[str, int \| float]` | Tracked numerical stats — any measurable quantity, including physical stats like body weight (e.g. `{"hp": 80, "reputation": 30, "weight_kg": 62}`); empty by default. Diffs merge entries instead of replacing the map |
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

All options below are read through the fabricatio configuration chain (see the
[Configuration Guide](../../docs/source/configuration.rst)). Set them under the
`[ext.character]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.character]` in `pyproject.toml`, or via
`FABRICATIO_EXT__CHARACTER__<FIELD_UPPER>` environment variables.

```toml
[ext.character]
mind_personality_high = 70.0
```

| Option | Type | Default | Description |
|---|---|---|---|
| `render_character_card_template` | `str` | `"built-in/render_character_card"` | Template to use for rendering character cards. |
| `mind_system_prompt_template` | `str` | `"built-in/mind_system_prompt"` | Handlebars template for as_prompt() system prompt rendering. |
| `mind_threat_analysis_template` | `str` | `"built-in/mind_threat_analysis"` | Template for 'which need is threatened' LLM call. |
| `mind_fulfill_analysis_template` | `str` | `"built-in/mind_fulfill_analysis"` | Template for 'which need is fulfilled' LLM call. |
| `mind_bias_judgment_template` | `str` | `"built-in/mind_bias_judgment"` | Template for cognitive distortion judgment LLM call. |
| `mind_impact_analysis_template` | `str` | `"built-in/mind_impact_analysis"` | Template for emotion/intensity/personality_shift LLM call. |
| `mind_personality_high` | `float` | `70.0` | BigFive score above this = 'high' trait. |
| `mind_personality_low` | `float` | `30.0` | BigFive score below this = 'low' trait. |
| `mind_emotion_intensity_high` | `float` | `70.0` | Emotion intensity above this triggers high-arousal behavior. |
| `mind_emotion_intensity_mid` | `float` | `40.0` | Emotion intensity above this triggers mild emotional coloring. |
| `mind_satisfaction_threshold` | `int` | `3` | Accumulated positive events needed to rise one Maslow level. |
| `mind_age_brackets` | `Tuple[Tuple[int, float], ...]` | `(see config.py)` | Age brackets and their personality shift multipliers. |
| `mind_need_focus` | `Dict[MaslowLevel, str]` | `(see config.py)` | Maslow level -> behavioral description for prompt injection. |
| `mind_bias_examples` | `Dict[Distortion, str]` | `(see config.py)` | Cognitive distortion -> example internal monologue. |
| `mind_personality_rules` | `Dict[PersonalityFlag, str]` | `(see config.py)` | Personality flag key -> behavioral description for prompt injection. |
| `mind_emotion_somatic_map` | `Dict[Emotion, Tuple[SomaticState, SomaticState]]` | `(see config.py)` | Emotion keyword -> (high_intensity_body, low_intensity_body) mapping. |
| `mind_diamonds_template` | `str` | `"built-in/mind_diamonds_analysis"` | Template for DIAMONDS 8-dim situation extraction. |
| `mind_diamonds_distortion_boost` | `Dict[SituationDimension, Dict[Distortion, float]]` | `(see config.py)` | DIAMONDS dimension -> {distortion: score_boost} mapping for rule_filter. |
| `mind_cbt_confidence_threshold` | `float` | `70.0` | If rule_filter top distortion score > this, use rule result directly; else full LLM. |
| `mind_suffering_intensity_threshold` | `float` | `80.0` | Emotion intensity above this triggers suffering creation. |
| `mind_suffering_template` | `str` | `"built-in/mind_suffering_analysis"` | Template for LLM-generated suffering narrative. |
| `mind_style_extraction_template` | `str` | `"built-in/mind_style_extraction"` | Template for extracting linguistic style from dialogues. |

Access at runtime: `from fabricatio_character.config import character_config`.

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
    print(c.name, "-", c.activated_role)
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

## Mental Engine

`MentalState` models how a character *changes*: a stable identity layer (Big Five
personality, CBT distortion tendencies, linguistic style, age), a volatile
per-event emotional layer (emotion, somatic response, active distortion,
DIAMONDS situation), an accumulated Maslow need layer, and irreversible
traumas.

The state object is self-sufficient and mirrors the `CharacterCard` conventions:

| Surface | Owner | Role |
|---|---|---|
| `apply(impact)` | `MentalState` | Deterministic rules: need threat drop / satisfaction rise, age-scaled personality drift, suffering accumulation, emotion + somatic replacement. Copy-on-write — returns a new instance |
| `as_prompt()` | `MentalState` | Renders the psychology block via `mind_system_prompt_template` (AsPrompt protocol) |
| `persist()` / `from_persistent()` | `MentalState` | Checkpoint / restore (PersistentAble) |
| `from_card(card, age=25)` | `MentalState` | No-LLM seed; bridges the card's `mood` text to an `Emotion` when it names one |
| `seed_from(card, age=25)` | `UseMind` | LLM-judged seed: need level from `card.want`, distortion tendencies from `card.flaw` |
| `observe(event, state)` | `UseMind` | Pure analysis → `EventImpact`: threatened/fulfilled need, emotion + intensity, DIAMONDS situation, distortion (rule filter + confidence-gated LLM judgment), suffering on high intensity |
| `react(event, state)` | `UseMind` | One-call `observe` + `apply` |
| `extract_style(name, dialogues)` | `UseMind` | Linguistic style extraction from dialogue history |

### Usage

```python
from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_character.capabilities.mental import UseMind
from fabricatio_character.utils import dump_card


class StoryTeller(CharacterCompose, UseMind, ...):
    """Writes in-character; keeps psychology evolving per event."""


agent = StoryTeller("storyteller")
card = await agent.compose_characters("Hamlet, prince of Denmark")
mind = await agent.seed_from(card, age=30)

mind = await agent.react("The ghost of your father accuses your uncle.", mind)
prompt = dump_card(card) + "\n\n" + mind.as_prompt()
reply = await agent.aask("What do you say to your mother?", system_prompt=prompt)

mind.persist("checkpoints/minds/")
```

`age` lives on the state (`CharacterMind.age`) and scales personality drift:
child 3.0×, adolescent 1.5×, young adult 0.5×, adult 0.2×
(`mind_age_brackets`).

### Research Foundations

| Paper | Year | Contribution |
|---|---|---|
| Costa & McCrae (Big Five) | 1992 | Personality model |
| Maslow | 1943 | Need hierarchy |
| Beck / Burns (CBT) | 1976/1980 | Cognitive distortions |
| Rauthmann et al. (DIAMONDS) | 2014 | Situation classification |
| Zhan et al. (TTM) | 2025 | Linguistic style decoupling |
| Du et al. (EFT-CoT) | 2026 | Embodied perception |
| Emotional Cost Functions | 2026 | Irreversible trauma |

---

## License

MIT — see [LICENSE](LICENSE)
