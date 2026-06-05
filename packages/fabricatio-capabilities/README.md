# `fabricatio-capabilities`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-capabilities)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-capabilities)](https://pypi.org/project/fabricatio-capabilities/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-capabilities/week)](https://pepy.tech/projects/fabricatio-capabilities)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-capabilities)](https://pepy.tech/projects/fabricatio-capabilities)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

High-level LLM agent capabilities for structured extraction, content rating, sequence ordering, and task dispatch. Built on `fabricatio-core`.

## Installation

```bash
pip install fabricatio[capabilities]
# or
uv pip install fabricatio[capabilities]
```

For the full Fabricatio suite:

```bash
pip install fabricatio[full]
```

## Overview

`fabricatio-capabilities` provides opinionated, composable mixins that give agents higher-level reasoning abilities:

- **Extract** structured data from unstructured text into Pydantic models.
- **Rate** content against multi-criteria rubrics, including automated criteria drafting, weighted composite scoring, and top-*k* selection.
- **Order** sequences of items (strings or `WithBriefing` objects) by a requirement or by computed scores.
- **Propose & dispatch** tasks to candidate roles based on semantic matching.
- **Patch** and **persist** Pydantic models with type-safe update mechanisms.

Every capability is an ABC mixin — subclass alongside your agent's base to compose exactly the abilities you need.

## Package Structure

```
fabricatio_capabilities/
 ├── capabilities/         # Mixin classes
 │   ├── extract.py        # Extract — structured extraction from text
 │   ├── rating.py         # Rating — multi-criteria rating, criteria drafting, composite scoring, best-k selection
 │   ├── order.py          # Ordering — LLM-based and score-based sequence ordering
 │   └── task.py           # ProposeTask, DispatchTask — task proposal and delegation
 ├── models/               # Reusable Pydantic base models
 │   ├── generic.py        # Patch, SequencePatch, PersistentAble, FinalizedDumpAble, ModelHash, UpdateFrom, etc.
 │   └── kwargs_types.py   # TypedDict kwargs: CompositeScoreKwargs, OrderStringKwargs, ReferencedKwargs
 └── config.py             # Template name configuration (CapabilitiesConfig)
```

## Key Classes

### Capabilities

| Class | Base | Purpose |
|-------|------|---------|
| `Extract` | `Propose` | Extracts one or more Pydantic model instances from a string or list of strings. Uses configurable prompt templates. |
| `Rating` | `Propose` | Fine-grained rating against a manual and score range. Can draft rating manuals, criteria, and weights (Klee method AHP). Computes composite scores and picks best-*k* candidates. |
| `Ordering` | `Rating` | Orders a sequence of strings or `WithBriefing` items by a natural-language requirement or by computed composite scores. |
| `ProposeTask` | `Propose` | Proposes a `Task` object from a natural-language prompt. |
| `DispatchTask` | `UseLLM` | Dispatches a `Task` to the best-matching candidate `Role` based on briefing text and event subscriptions. |

### Models

| Class | Purpose |
|-------|---------|
| `Patch[T]` | Type-safe field-level updates to a target Pydantic model. Fields present on the patch are copied onto the target. Supports JSON schema generation with reference-class documentation. |
| `SequencePatch[T]` | Patch for sequences of objects carrying a `tweaked` list. |
| `ProposedUpdateAble` | Combines `SketchedAble` + `UpdateFrom` — allows an object to be updated in-place from a proposed replacement. |
| `FinalizedDumpAble` | JSON serialization with alias support and direct file writing. |
| `PersistentAble` | Save to / load from a file path with BLAKE3 content hashing and JSON serialization. |
| `ModelHash` | Consistent `__hash__` based on `model_dump_json()`. |
| `UpdateFrom` | Abstract base for in-place updates with type-checked pre-validation. |
| `AsPrompt` | Converts a model instance into an LLM prompt string. |
| `WordCount` | Mixin providing word count tracking for models. |

### Configuration

`CapabilitiesConfig` (accessible as `capabilities_config`) holds template name defaults for all capability operations: extraction, dispatch, rating, criteria drafting, and ordering.

### Kwargs Types

`CompositeScoreKwargs`, `BestKwargs`, `OrderStringKwargs`, `ReferencedKwargs[T]` — TypedDicts that extend `ValidateKwargs` with capability-specific parameters (topic, criteria, weights, manual, reference).

## Usage

### Structured Extraction

```python
from pydantic import BaseModel
from fabricatio_capabilities.capabilities.extract import Extract

class Person(BaseModel):
    name: str
    age: int

class MyAgent(Extract, YourBaseAgent):
    ...

agent = MyAgent()
person = await agent.extract(Person, "Alice is 30 years old.")
assert person.name == "Alice"
```

### Multi-Criteria Rating

```python
from fabricatio_capabilities.capabilities.rating import Rating

class MyAgent(Rating, YourBaseAgent):
    ...

agent = MyAgent()
manual = await agent.draft_rating_manual("essay quality", {"clarity", "argument"})
scores = await agent.rate("The essay is well-structured.", manual, (0.0, 10.0))
```

### Sequence Ordering

```python
from fabricatio_capabilities.capabilities.order import Ordering

class MyAgent(Ordering, YourBaseAgent):
    ...

agent = MyAgent()
ordered = await agent.order(
    ["clean kitchen", "buy groceries", "pay bills"],
    "by urgency",
)
```

### Task Dispatch

```python
from fabricatio_capabilities.capabilities.task import ProposeTask, DispatchTask

class MyAgent(ProposeTask, DispatchTask, YourBaseAgent):
    ...

agent = MyAgent()
task = await agent.propose_task("Summarize this document.")
result = await agent.dispatch_task(task, candidates={role_a, role_b})
```

### Patching Models

```python
from pydantic import BaseModel
from fabricatio_capabilities.models.generic import Patch

class User(BaseModel):
    name: str
    age: int
    email: str = ""

class UserPatch(Patch[User], BaseModel):
    name: str | None = None
    email: str | None = None

user = User(name="Alice", age=30)
patch = UserPatch(name="Bob")
updated = patch.apply(user)
assert updated.name == "Bob" and updated.age == 30
```

## Dependencies

- `fabricatio-core` — core interfaces (`Propose`, `UseLLM`, `Task`, `Role`, `TEMPLATE_MANAGER`)
- `orjson` — fast JSON serialization
- `pydantic` — model validation and schema generation
- `more-itertools` — utility iterators

## License

MIT — see [LICENSE](../../LICENSE)
