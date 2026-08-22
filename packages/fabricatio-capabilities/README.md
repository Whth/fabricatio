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


### Kwargs Types

`CompositeScoreKwargs`, `BestKwargs`, `OrderStringKwargs`, `ReferencedKwargs[T]` — TypedDicts that extend `ValidateKwargs` with capability-specific parameters (topic, criteria, weights, manual, reference).

## Configuration

All options below are read through the fabricatio configuration chain (see the
[Configuration Guide](../../docs/source/configuration.rst)). Set them under the
`[ext.capabilities]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.capabilities]` in `pyproject.toml`, or via
`FABRICATIO_EXT__CAPABILITIES__<FIELD_UPPER>` environment variables.

```toml
[ext.capabilities]
extract_template = "built-in/extract"
as_prompt_template = "built-in/as_prompt"
dispatch_task_template = "built-in/dispatch_task"
rate_fine_grind_template = "built-in/rate_fine_grind"
draft_rating_manual_template = "built-in/draft_rating_manual"
draft_rating_criteria_template = "built-in/draft_rating_criteria"
extract_reasons_from_examples_template = "built-in/extract_reasons_from_examples"
extract_criteria_from_reasons_template = "built-in/extract_criteria_from_reasons"
draft_rating_weights_klee_template = "built-in/draft_rating_weights_klee"
order_string_template = "built-in/order_string"
order_briefed_template = "built-in/order_briefed"
```

| Option | Type | Default | Description |
|---|---|---|---|
| `extract_template` | `str` | `"built-in/extract"` | The name of the extract template which will be used to extract model from string. |
| `as_prompt_template` | `str` | `"built-in/as_prompt"` | The name of the as prompt template which will be used to convert a string to a prompt. |
| `dispatch_task_template` | `str` | `"built-in/dispatch_task"` | The name of the dispatch task template which will be used to dispatch a task. |
| `rate_fine_grind_template` | `str` | `"built-in/rate_fine_grind"` | The name of the rate fine grind template which will be used to rate fine grind. |
| `draft_rating_manual_template` | `str` | `"built-in/draft_rating_manual"` | The name of the draft rating manual template which will be used to draft rating manual. |
| `draft_rating_criteria_template` | `str` | `"built-in/draft_rating_criteria"` | The name of the draft rating criteria template which will be used to draft rating criteria. |
| `extract_reasons_from_examples_template` | `str` | `"built-in/extract_reasons_from_examples"` | The name of the extract reasons from examples template which will be used to extract reasons from examples. |
| `extract_criteria_from_reasons_template` | `str` | `"built-in/extract_criteria_from_reasons"` | The name of the extract criteria from reasons template which will be used to extract criteria from reasons. |
| `draft_rating_weights_klee_template` | `str` | `"built-in/draft_rating_weights_klee"` | The name of the draft rating weights klee template which will be used to draft rating weights with Klee method. |
| `order_string_template` | `str` | `"built-in/order_string"` | The name of the order string template which will be used to order string. |
| `order_briefed_template` | `str` | `"built-in/order_briefed"` | The name of the order briefed template which will be used to order briefed. |


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
