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

## Mental Model Design Plan

> **Status**: Design phase — not yet implemented.
>
> This section documents the planned psychological state engine for dynamic character behavior. It extends `CharacterCard` (static snapshot) with `MentalState` (dynamic, event-driven).

### Problem

`CharacterCard` describes *who a character is* at a single point in time. It does not model *how a character changes* in response to events. A believable character needs:

- Stable personality traits that drift slowly under extreme events
- Motivation that shifts as needs are met or deprived
- Cognitive distortions that color how events are interpreted
- Emotional states with physical (somatic) manifestations
- Irreversible trauma that permanently reshapes behavior
- Linguistic style decoupled from cognitive content

### Architecture

Three-layer separation: **analysis** (LLM with schema) → **update** (deterministic rules) → **alignment** (prompt injection).

```
Event
  ↓
┌─────────────────────────────────────────────────────┐
│ Analysis Layer (LLM + Schema)                        │
│                                                     │
│  Event → DIAMONDS 8-dim → CBT distortion → Impact   │
└───────────────────────┬─────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Update Layer (Deterministic Rules)                   │
│                                                     │
│  BigFiveProfile  ← personality drift (age-scaled)   │
│  MaslowLevel     ← threat=d immediate drop,         │
│                     satisfaction=accumulation rise   │
│  SomaticState    ← emotion → body mapping           │
│  Suffering       ← permanent trauma accumulation    │
└───────────────────────┬─────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Alignment Layer (Prompt Injection)                   │
│                                                     │
│  MentalState → build_system_prompt() → LLM output   │
└─────────────────────────────────────────────────────┘
```

### Data Models

#### `BigFiveProfile` (stable)

5-dimensional personality coordinate. Each dimension 0–100.

| Dimension | Low | High |
|---|---|---|
| Openness (O) | Traditional, practical | Curious, imaginative |
| Conscientiousness (C) | Casual, flexible | Organized, disciplined |
| Extraversion (E) | Introverted, quiet | Outgoing, social |
| Agreeableness (A) | Competitive, skeptical | Cooperative, trusting |
| Neuroticism (N) | Emotionally stable | Anxious, volatile |

Personality drift is age-scaled: child (3.0×), adolescent (1.5×), young adult (0.5×), adult (0.2×).

#### `MaslowLevel` (dynamic)

Discrete need hierarchy. Character is "stuck" at the lowest unsatisfied level.

```
SELF_ACTUALIZATION (5)
  ↑
ESTEEM (4)
  ↑
BELONGING (3)
  ↑
SAFETY (2)
  ↑
PHYSIOLOGICAL (1)
```

Transition rules:
- **Drop**: instant on threat (fear-driven, one event suffices)
- **Rise**: gradual on satisfaction (accumulation ≥ 3 positive events)

#### `SituationProfile` — DIAMONDS Taxonomy (per-event)

8-dimensional situational classification (Rauthmann et al., 2014). Replaces boolean event flags.

| Dimension | Description |
|---|---|
| Duty | Obligation, responsibility |
| Intellect | Cognitive challenge |
| Adversity | Threat, hostility |
| Mating | Romantic/sexual context |
| pOsitivity | Positive valence |
| Negativity | Negative valence |
| Deception | Manipulation, betrayal |
| Sociality | Interpersonal interaction |

Each dimension scored 0–1 by LLM extraction.

#### `CognitiveDistortion` — CBT Framework (per-event)

Hybrid engine: rule-based filter (fast) + LLM refinement (accurate).

| Distortion | Description | Trigger |
---|---|---|
| Catastrophizing | Amplify threat | High Adversity |
| Black-and-white | No middle ground | High Deception |
| Personalization | Self-blame | High Negativity + Sociality |
| Emotional reasoning | Feelings = facts | High Negativity |
| Should-thinking | Rigid expectations | High Duty |

Confidence threshold: if top candidate score > 70 → rule result + monologue generation; else → full LLM analysis.

#### `SomaticState` — Embodied Perception (derived)

Body sensations derived from emotion type + intensity. Based on EFT-CoT framework (Du et al., 2026).

```python
class SomaticState:
    heart_rate: str      # normal / elevated / racing
    breathing: str       # normal / shallow / rapid
    muscle_tension: str  # relaxed / tense / trembling
    facial_expression: str  # neutral / frown / wide_eyes
    voice: str           # steady / trembling / fast
```

#### `QualitativeSuffering` — Irreversible Trauma (permanent)

Accumulates over time, never deleted. Based on Emotional Cost Functions (Mopgar, 2026).

```python
class QualitativeSuffering:
    what_was_lost: str         # What was taken
    the_void: str              # The gap it created
    how_it_changed_me: str     # How it reshaped the character
    anticipatory_dread: float  # Fear of similar situations (0–100)
```

Two pathways:
- **Experiential dread**: from character's own lived consequences
- **Pre-experiential dread**: acquired from others' stories or cultural knowledge

#### `LinguisticStyle` — Decoupled Expression (extracted)

Separates *what to say* from *how to say it*. Based on TTM (Zhan et al., 2025).

```python
class LinguisticStyle:
    preferences: str           # Natural language description
    common_pronouns: list[str] # e.g. ["我", "人家", "本座"]
    common_modals: list[str]   # e.g. ["应当", "必须", "或许"]
    common_adjectives: list[str]
    style_references: list[str] # Similar utterances from history
```

Extracted from character's historical dialogues via LLM analysis.

#### `MentalState` — Composite State

```python
class MentalState:
    personality: BigFiveProfile
    current_need: MaslowLevel
    satisfied_needs: list[MaslowLevel]
    emotion: str
    emotion_intensity: float
    cognitive_bias: str
    somatic_state: SomaticState
    sufferings: list[QualitativeSuffering]
    linguistic_style: LinguisticStyle
```

### Processing Pipeline

```python
async def process_event(engine: MindEngine, event: str) -> str:
    # 1. Analysis
    situation = await engine.analyze_situation(event)       # DIAMONDS
    distortion = await engine.analyze_distortion(           # CBT
        situation, engine.state.sufferings
    )

    # 2. Update (deterministic)
    impact = engine.compute_impact(situation, distortion)
    engine.apply_impact(impact)

    # 3. Alignment
    system_prompt = engine.build_system_prompt()

    # 4. Generation
    return await llm.generate(system=system_prompt, user=user_message)
```

### Prompt Injection

`build_system_prompt()` translates `MentalState` into LLM hard constraints:

| Component | Constraint Example |
---|---|
| Personality | "You tend to anxiety, amplify threats, assume the worst" |
| Need focus | "You crave acceptance; loneliness is your greatest fear" |
| Emotion style | "Current: fear (85/100) — speak fast, short sentences, may stutter" |
| Cognitive bias | "Catastrophizing: 'He said something rude → he must hate me → everyone will leave'" |
| Somatic state | "Heart racing, hands trembling, voice shaking" |
| Suffering | "Lost trust before → over-guarded in similar situations" |
| Linguistic style | "Prefers rhetorical questions, long sentences, occasional classical Chinese" |

### Evaluation Framework

Three-layer validation based on EMgine methodology (Smith, 2023):

| Layer | Method | Target |
---|---|---|
| Theory consistency | Automated assertions | > 90% pass rate |
| Reader perception | LLM-as-Judge + human | > 7.5/10 |
| Trajectory consistency | Jump/reversal detection | No anomalies |

Test suite uses literary characters as baseline (Hamlet, Lin Daiyu, Julien Sorel).

### Research Foundations

| Paper | Year | Contribution |
---|---|---|
| Costa & McCrae (Big Five) | 1992 | Personality model |
| Maslow | 1943 | Need hierarchy |
| Beck / Burns (CBT) | 1976/1980 | Cognitive distortions |
| Rauthmann et al. (DIAMONDS) | 2014 | Situation classification |
| Zhan et al. (TTM) | 2025 | Linguistic style decoupling |
| Du et al. (EFT-CoT) | 2026 | Embodied perception |
| Mopgar (Emotional Cost Functions) | 2026 | Irreversible trauma |
| Smith (EMgine) | 2023 | Evaluation methodology |

### Implementation Roadmap

See [root README TODO](../../README.md) for detailed task breakdown under "Character system completion → Mental model".

---

## License

MIT — see [LICENSE](LICENSE)
