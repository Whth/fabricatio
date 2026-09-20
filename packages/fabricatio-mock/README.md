# `fabricatio-mock`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-mock)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-mock)](https://pypi.org/project/fabricatio-mock/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-mock/week)](https://pepy.tech/projects/fabricatio-mock)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-mock)](https://pepy.tech/projects/fabricatio-mock)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Test utilities and mock implementations for fabricatio. Provides configurable dummy LLM,
embedding, and reranker responses so you can test agent workflows without real API calls.

---

## Installation

```bash
pip install fabricatio[mock]
# or
uv pip install fabricatio[mock]
```

For a full installation that includes this package and all other components:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

---

## Quick Start

The primary API uses `install_router_usage` (a context manager) with `return_router_usage`
to inject dummy responses into the Rust-side router singleton:

```python
import pytest
from fabricatio_mock.utils import install_router_usage
from fabricatio_mock.models.mock_router import return_router_usage


@pytest.mark.asyncio
async def test_my_role():
    # Responses are returned in FIFO order across calls.
    # Each is padded automatically to cover retries.
    with install_router_usage(*return_router_usage("Hello", "World")):
        result = await some_llm_call(question="greet")
        assert result == "Hello"

        result = await some_llm_call(question="farewell")
        assert result == "World"
```

### Unique question strings

The router uses a persistent response cache keyed by request hash. **Every test case MUST use a unique `question` string** to avoid stale cache hits from previous tests:

```python
# GOOD - unique questions per test case
@pytest.mark.parametrize("expected", ["Hi", "Hello"])
async def test_greeting(expected):
    with install_router_usage(*return_router_usage(expected)):
        result = await role.aask(
            send_to="openai/gpt-3.5-turbo",
            question=f"q_greeting_{expected}",  # unique per parametrize case
        )
        assert result == expected


# BAD - "Hi" and "Hello" collide across parametrize cases
@pytest.mark.parametrize("expected", ["Hi", "Hello"])
async def test_greeting_bad(expected):
    with install_router_usage(*return_router_usage(expected)):
        result = await role.aask(
            send_to="openai/gpt-3.5-turbo",
            question="test",  # same hash -> stale cache hit
        )
        assert result == expected
```

---

## Usage Recipes

Complete, copy-pasteable tests: swap in your own capability and run.

### 1. Script an LLM capability

```python
from fabricatio_mock import MockScript, make_test_role

role = make_test_role(name="writer")


async def test_greeting() -> None:
    with MockScript.from_texts("Hello", "World"):
        assert await role.aask(question="greet") == "Hello"
        assert await role.aask(question="farewell") == "World"
```

`make_test_role` routes to the dummy group and sets `llm_no_cache=True` together with `llm_no_store=True`
(and their embedding/reranker twins), so a script pops its queue even when the same question was asked by
an earlier run — and no canned answer or dummy vector enters the shared cache for a later live request to
pick up.

### 2. Fail loudly on a miscounted script

Scripts are strict: nothing is padded in behind your back. One call more than declared raises
`ScriptExhaustedError`, whose message names every declared response:

```python
import pytest
from fabricatio_mock import MockScript, ScriptExhaustedError, Value, make_test_role

role = make_test_role(name="writer")


async def test_miscounted_script() -> None:
    script = MockScript.from_values(Value.from_text("only", name="metadata"))

    with pytest.raises(ScriptExhaustedError), script:
        await role.aask(question="first")
        await role.aask(question="second")
```

```text
MockScript exhausted: the code under test requested more LLM responses than the 1 declared for group 'llm':
MockScript(group='llm', padding=0):
  1. metadata
Declare the missing response, or opt into silent repeats with .with_padding(n).
```

Reach for `.with_padding(n)` when extra calls are legitimate, for example retries.

### 3. Script a `propose` call

`Value.from_model` scripts the JSON that a Pydantic-model proposal expects:

```python
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.generic import SketchedAble
from fabricatio_mock import MockScript, Value, make_test_role


class Plan(SketchedAble):
    """A one-field plan used by the example."""

    title: str


role = make_test_role(Propose, name="planner")


async def test_propose() -> None:
    with MockScript.from_values(Value.from_model(Plan(title="Chapter 1"), name="plan")):
        plan = await role.propose(Plan, "one chapter about the sea")

    assert plan is not None
    assert plan.title == "Chapter 1"
```

Models proposed through fabricatio derive from `SketchedAble`, which supplies the JSON prompt.

### 4. Deterministic embeddings and reranks

No hand-written vectors or index tuples; derive them from the inputs:

```python
import pytest
from fabricatio_core import rust
from fabricatio_mock import hash_embedding, install_fake_embeddings, install_fake_reranks


async def test_vector_calls() -> None:
    texts = ["rust book", "python book"]

    with install_fake_embeddings(texts, ndim=4):
        vectors = await rust.ROUTER.embedding("embedding", texts, 4, no_cache=True, no_store=True)

    assert vectors[0] == pytest.approx(hash_embedding(texts[0], ndim=4), rel=1e-6)

    query = "rust handbook"
    documents = ["python guide", "rust handbook"]

    with install_fake_reranks((query, documents)):
        ranking = await rust.ROUTER.rerank("reranker", query, documents, no_cache=True, no_store=True)

    assert ranking[0][0] == 1  # "rust handbook" covers the query token
```

`no_cache`/`no_store` keep requests out of the persistent cache (a `make_test_role` role sets them for
you), and vectors round-trip as `f32`, hence `pytest.approx`. Through a capability instead of the router,
the same seeds serve `role.vectorize(texts, send_to="embedding", ndim=4)` and
`role.arank(query, documents, send_to="reranker")`.

### 5. Stub templates and config copies

```python
import dataclasses

from fabricatio_mock import stub_template

# `module` is the module whose binding the code under test reads, for example
# `from fabricatio_diff.capabilities import hashline_edit as module`
name = stub_template("test_hashline_diff", "SOURCE:\n{{source}}")


def test_diff_renders_stub(monkeypatch):
    patched = dataclasses.replace(module.diff_config, hashline_diff_template=name)
    monkeypatch.setattr(module, "diff_config", patched)
    # the capability now renders the stub instead of the packaged template
```

`stub_template` writes the `.hbs` file with LF endings and registers its directory as a template store.
Config overrides stay with the native tools: `dataclasses.replace(cfg, field=value)` for dataclass
configs, and `clone = cfg.model_copy(deep=True); clone.field = value` for pydantic ones. pytest's
`monkeypatch` installs the copy and restores the original at the end of the test.

### 6. Use the pytest fixtures

```python
async def test_propose(mock_role, mock_script):
    role = mock_role(Propose, name="planner")

    with mock_script.from_values(Value.from_model(Plan(title="Chapter 1"), name="plan")):
        plan = await role.propose(Plan, "one chapter about the sea")

    assert plan is not None
```

The fixtures are inert until a suite loads the plugin: `pytest -p fabricatio_mock.pytest_plugin`, or one
line in the suite's `conftest.py` (`pytest_plugins = ["fabricatio_mock.pytest_plugin"]`).

### Replacing the older patterns

| Older pattern | With |
|---|---|
| `with install_router_usage(*return_mixed_router_usage(Value(...), ...)):` | `with MockScript.from_values(...):` (strict, named, chainable) |
| `class DeckRole(LLMTestRole, GenerateDeck): ...` plus a `role` fixture | `make_test_role(GenerateDeck, name="deck")`, or the `mock_role` fixture |
| `TEMPLATE_MANAGER.add_store(tmp_path)` plus hand-rolled template files | `stub_template(...)` |
| `monkeypatch.setattr(mod, "cfg", dataclasses.replace(cfg, ...))` | unchanged; `stub_template` returns the name to pass into the replace |
| Hand-written embedding vectors | `install_fake_embeddings([...], ndim=n)` |
| Hand-written `(index, score)` tuples | `install_fake_reranks((query, documents))` |
| `return_router_usage(json.dumps(obj))` | `return_obj_router_usage(obj)` |
| `Value(source=text, type="raw", convertor=lambda s: s)` | `Value.from_text(text)` |

---

## Response Builders

All `return_*_router_usage` functions return a `list[str]` ready to unpack into `install_router_usage`.

| Function | Description |
:|---|---|
| `return_router_usage(*values, default=, padding=)` | Plain string responses. `default` defaults to the last value; `padding` (default 10) appends extra copies for retry safety. |
| `return_json_router_usage(*jsons, default=, padding=)` | Wraps each string in a ` ```json ` code block. |
| `return_code_router_usage(*codes, lang=, default=, padding=)` | Wraps each string in a fenced code block with the given `lang`. |
| `return_python_router_usage(*codes, default=, padding=)` | Shorthand for `return_code_router_usage(..., lang="python")`. |
| `return_json_obj_router_usage(*objs, default=, padding=)` | Serializes objects with `orjson` then wraps in a JSON code block. |
| `return_obj_router_usage(*objs, default=, padding=)` | Serializes objects with `orjson` **without** a fence (for parsers that accept raw JSON). |
| `return_model_json_router_usage(*models, default=, padding=)` | Serializes Pydantic models via `model_dump(by_alias=True)` then wraps in a JSON code block. |
| `return_generic_router_usage(*strings, lang=, default=, padding=)` | Wraps each string in `--- Start of {lang} ---` / `--- End of {lang} ---` delimiters. |
| `return_mixed_router_usage(*values, default=, padding=)` | Accepts `Value` dataclass instances for mixed-type responses in a single sequence. |

### `Value` dataclass

For tests that need different response formats within a single sequence:

```python
from fabricatio_mock.models.mock_router import Value, return_mixed_router_usage
from fabricatio_mock.utils import install_router_usage

with install_router_usage(*return_mixed_router_usage(
    Value(source='{"key": "val"}', type="json"),
    Value(source='print("hi")', type="python"),
    Value(source="raw text", type="raw", convertor=lambda s: s.upper()),
)):
    ...
```

Type options: `"model"`, `"json"`, `"python"`, `"generic"`, `"raw"`. When a `convertor` callable is provided, it takes precedence over the type-based conversion.

### `Value` factories

Named constructors for the five payload shapes, so tests stop hand-writing fences:

```python
from fabricatio_mock import Value

Value.from_text("plain response")                # no fence, no conversion
Value.from_model(plan, name="metadata")          # pretty JSON of model_dump(by_alias=True)
Value.from_json({"tag": "rust"})                 # pretty JSON of any JSON value
Value.from_python("x = 1")                       # ```python fence
Value.from_generic("body")                       # --- Start of string --- block
Value.from_raw("HELLO", convertor=str.lower)     # rendered through a convertor
```

`Value.from_text` exists because `Value(source=..., type="raw")` raises at rendering time unless a
`convertor` is supplied. The optional `name` labels the response in `MockScript` failure reports.

### `pad_responses`

The low-level padding helper used by all `return_*` functions. DummyModel errors when its internal queue is exhausted; padding with extra copies of the default value covers retries (`max_validations`) and batch calls.

```python
from fabricatio_mock.models.mock_router import pad_responses

# Returns ["Hello", "World", "World", "World", ...] (last value repeated 10 times)
pad_responses("Hello", "World", default="Fallback", padding=3)
```

---

## Response Scripts

`MockScript` declares an ordered, *named* set of responses. Unlike a bare
`install_router_usage(*responses)`, a script installs strictly (no silent padding) and
an exhausted script fails with the declared names instead of a bare queue error:

```python
from fabricatio_mock import MockScript, Value

script = MockScript.from_values(Value.from_model(plan, name="metadata")).with_text("chapter one prose")

with script:
    ...  # every LLM call pops the next declared response
```

| Factory / mutator | Effect |
|---|---|
| `MockScript.from_texts(*texts)` | Plain-text responses, auto-labelled `text-1`, `text-2`, ... |
| `MockScript.from_values(*values)` | Responses from `Value` objects (label = `value.name`) |
| `.with_text(text, name=)`, `.with_values(*values)` | Append responses (chainable, returns a new script) |
| `.with_padding(n)` | Repeat the last response `n` times (opt into the lenient behaviour) |
| `.with_group(group)` | Deploy to another route group |
| `.with_reset_on_exit()` | Empty the group's queue when the block exits |
| `.describe()` | List the declared responses (also used in failure reports) |

The router binding exposes no way to read the remaining queue, so a script reports
over-consumption (declared responses exhausted) but not under-consumption.
`clear_dummy_responses(group)` empties a queue explicitly.

---

## Test Roles

Pre-configured roles for testing LLM and Propose capabilities:

```python
from fabricatio_mock.models.mock_role import LLMTestRole, ProposeTestRole

role = LLMTestRole.with_bio(name="tester")
# llm_send_to defaults to "llm" (fabricatio_mock.DUMMY_LLM_GROUP)
# llm_no_cache and llm_no_store default to True, as do the embedding_/reranker_ twins
```

| Class | Bases | Purpose |
:|---|---|---|
| `LLMTestRole` | `Role`, `UseLLM` | Role with LLM calling capability; `llm_send_to` targets the dummy LLM group, and the `*_no_cache`/`*_no_store` flags default to `True` so no dummy answer or vector enters the shared cache. |
| `ProposeTestRole` | `LLMTestRole`, `Propose` | Extends `LLMTestRole` with the `Propose` capability. |

### Composed test roles

`make_test_role` composes the class per capability combination instead of one empty class per package:

```python
from fabricatio_mock import make_test_role

role = make_test_role(GenerateDeck, name="deck")   # == class GenerateDeckTestRole(LLMTestRole, GenerateDeck)
```

The composed class is memoized per capability tuple, so repeated calls reuse a single type.

---

## Pytest Plugin

The fixtures live in `fabricatio_mock.pytest_plugin` and load only when a suite asks for them, so
installing the package registers nothing. Load the module with
`pytest -p fabricatio_mock.pytest_plugin`, or from the suite's `conftest.py`:

```python
pytest_plugins = ["fabricatio_mock.pytest_plugin"]
```

Every fixture stays inert until a test requests it:

| Fixture | Provides |
|---|---|
| `mock_role` | The `make_test_role` factory. |
| `mock_script` | The `MockScript` class. |
| `stub_template` | `stub_template(name, body)` writing into a session-scoped store. |

```python
async def test_deck(mock_role, mock_script):
    role = mock_role(GenerateDeck, name="deck")
    with mock_script.from_texts("[]"):
        ...
```

---

## Helper Utilities

| Function | Description |
:|---|---|
| `install_router_usage(*responses, group=)` | Context manager: configures the router singleton with dummy LLM responses. Restorable by the caller after `with` block exit. |
| `setup_dummy_responses(*responses, group=)` | Same as above but not a context manager — permanent until the next call. |
| `clear_dummy_responses(group=)` | Empties a dummy completion queue so later calls fail loudly instead of consuming leftovers. |
| `code_block(content, lang)` | Wraps `content` in a fenced code block: ` ```{lang}\n{content}\n``` `. |
| `generic_block(content, lang)` | Wraps `content` in `--- Start of {lang} ---` / `--- End of {lang} ---` delimiters. |
| `make_roles(names, role_cls)` | Creates a list of `Role` instances from a list of names. |
| `make_n_roles(n, role_cls)` | Creates `n` `Role` instances with auto-generated names (`"Role 1"`, `"Role 2"`, …). |
| `make_test_role(*capabilities, name=)` | Composes `LLMTestRole` with capability mixins (memoized per combination). |
| `setup_dummy_embeddings(*embeddings, group=, model_id=)` | Configures the router with dummy embedding vectors (permanent). |
| `install_dummy_embeddings(*embeddings, group=, model_id=)` | Context manager version of `setup_dummy_embeddings`. |
| `setup_dummy_reranks(*rankings, group=, model_id=)` | Configures the router with dummy reranker ranking tuples (permanent). |
| `install_dummy_reranks(*rankings, group=, model_id=)` | Context manager version of `setup_dummy_reranks`. |
| `hash_embedding(text, ndim=, salt=)` | Deterministic unit vector for a text. |
| `rank_by_overlap(query, documents)` | `(index, score)` pairs sorted by query-token coverage. |
| `setup_fake_embeddings(*batches, ndim=, salt=)` / `install_fake_embeddings(...)` | Seeds hash-derived embedding batches (permanent / context manager). |
| `setup_fake_reranks(*calls)` / `install_fake_reranks(*calls)` | Seeds overlap-based rankings from `(query, documents)` pairs. |
| `stub_template(name, body, directory=)` | Writes a stub `.hbs` and registers its directory as a template store. |

---

## Embedding & Rerank Mocking

In addition to completion mocking, `fabricatio-mock` supports embedding and reranker mocking.

### Constants

| Constant | Default Value | Description |
|---|---|---|
| `DUMMY_LLM_GROUP` | `"llm"` | Default router group for mock LLM models. |
| `DUMMY_EMBEDDING_GROUP` | `"embedding"` | Default router group for mock embedding models. |
| `DUMMY_RERANKER_GROUP` | `"reranker"` | Default router group for mock reranker models. |

### Embedding Mock Example

```python
from fabricatio_mock.utils import install_dummy_embeddings
from fabricatio_mock.models.mock_router import pad_embeddings

# Create padded embedding responses (handles retries/batches)
embeddings = pad_embeddings([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])

with install_dummy_embeddings(*embeddings):
    result = await router.embedding("embedding/dummy/test-embedding-model", ["hello world"])
    assert result[0] == [1.0, 0.0, 0.0]
```

### Rerank Mock Example

```python
from fabricatio_mock.utils import install_dummy_reranks
from fabricatio_mock.models.mock_router import pad_rankings

# Create padded ranking responses
rankings = pad_rankings((0, 0.95), (1, 0.5))

with install_dummy_reranks(*rankings):
    result = await router.rerank("reranker/dummy/test-reranker-model", "query", ["doc1", "doc2"])
    assert result == [(0, 0.95)]
```

### Pad Functions

| Function | Description |
:|---|---|
| `pad_embeddings(*embeddings, default=, padding=)` | Pads embedding vectors with copies of the default (defaults to last value) for DummyModel safety. |
| `pad_rankings(*rankings, default=, padding=)` | Pads ranking tuples with copies of the default (defaults to last value) for DummyModel safety. |

### Deterministic Fakes

Hand-written vectors and index tuples make vector-store tests unreadable and run-order dependent, so the
fakes derive both from the declared inputs:

```python
from fabricatio_mock import hash_embedding, install_fake_embeddings, install_fake_reranks, rank_by_overlap

hash_embedding("alpha", ndim=4)                                    # unit vector, identical across runs
rank_by_overlap("rust book", ["python guide", "rust book review"]) # -> [(1, 1.0), (0, 0.0)]

with install_fake_embeddings(["alpha", "beta"], ndim=4):           # one call carrying two texts
    ...

with install_fake_reranks(("rust", ["python guide", "rust handbook"])):   # one call
    ...
```

`install_fake_embeddings` takes one argument per embedding call — a string is a single-text call, a
sequence is a batch call. `install_fake_reranks` takes `(query, documents)` pairs. The Rust side stores
vectors as `f32`, so compare returned values with `pytest.approx`. Embeddings and reranks share the same
persistent cache as completions (keyed by text and by query+documents); pass `no_cache=True, no_store=True`
on a direct `ROUTER` call — a `make_test_role` role sets the same flags for its capability calls — so the
seeded queue answers and no dummy vector is left behind for a live request.

---

## Template & Config Plumbing

Stub templates plus the native override path:

```python
import dataclasses

from fabricatio_mock import stub_template

name = stub_template("test_precise_chunk", "GUIDELINE: {{guideline}}")

# `module` is the module whose binding the code under test actually reads
monkeypatch.setattr(module, "rag_config", dataclasses.replace(module.rag_config, precise_chunk_template=name))
```

`stub_template` writes `<name>.hbs` into a store directory (a fresh temporary one by default) and
registers it with `TEMPLATE_MANAGER`; the store stays registered for the session, because the manager
exposes no way to unbind one. The override itself stays native: `dataclasses.replace(cfg, field=value)`
for dataclass configs, `clone = cfg.model_copy(deep=True)` plus direct assignment for pydantic ones.
pytest's `monkeypatch` installs the copy and restores the original binding when the test ends.

---

## How It Works

fabricatio delegates LLM calls to a Rust-side singleton router (`rust.ROUTER`).
`install_router_usage` mutates this singleton in-place by:

1. Registering a `DummyProvider` via `rust.ROUTER.add_provider(ProviderType.Dummy)`
2. Deploying a `DummyModel` with the given responses to a route group

Responses are reversed before storing because `DummyModel` uses LIFO (`Vec::pop`) internally.
The builder functions reverse them so callers get FIFO semantics.

Because the router is a shared `Arc`, all code paths that call through `router_usage.ask()`
see the injected responses automatically.

The `padding` parameter (default 10) appends extra copies of the default value to each
response list. This prevents `DummyModel` errors when the model is called more times than
expected — for example, during retries from `max_validations` or batched calls.

---

## Configuration

All options below are read through the fabricatio configuration chain (see the
[Configuration Guide](../../docs/source/configuration.rst)). Set them under the
`[ext.mock]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.mock]` in `pyproject.toml`, or via
`FABRICATIO_EXT__MOCK__<FIELD_UPPER>` environment variables.

```toml
[ext.mock]
```

The schema currently defines no options and is reserved for future use.

Access at runtime: `from fabricatio_mock.config import mock_config`.

---

## License

MIT — see [LICENSE](LICENSE)
