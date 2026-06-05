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

## Response Builders

All `return_*_router_usage` functions return a `list[str]` ready to unpack into `install_router_usage`.

| Function | Description |
|---|---|
| `return_router_usage(*values, default=, padding=)` | Plain string responses. `default` defaults to the last value; `padding` (default 10) appends extra copies for retry safety. |
| `return_json_router_usage(*jsons, default=, padding=)` | Wraps each string in a ` ```json ` code block. |
| `return_code_router_usage(*codes, lang=, default=, padding=)` | Wraps each string in a fenced code block with the given `lang`. |
| `return_python_router_usage(*codes, default=, padding=)` | Shorthand for `return_code_router_usage(..., lang="python")`. |
| `return_json_obj_router_usage(*objs, default=, padding=)` | Serializes objects with `orjson` then wraps in a JSON code block. |
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

### `pad_responses`

The low-level padding helper used by all `return_*` functions. DummyModel errors when its internal queue is exhausted; padding with extra copies of the default value covers retries (`max_validations`) and batch calls.

```python
from fabricatio_mock.models.mock_router import pad_responses

# Returns ["Hello", "World", "World", "World", ...] (last value repeated 10 times)
pad_responses("Hello", "World", default="Fallback", padding=3)
```

---

## Test Roles

Pre-configured roles for testing LLM and Propose capabilities:

```python
from fabricatio_mock.models.mock_role import LLMTestRole, ProposeTestRole

role = LLMTestRole.with_bio(name="tester")
# llm_send_to defaults to "llm" (fabricatio_mock.DUMMY_LLM_GROUP)
# llm_no_cache defaults to True
```

| Class | Bases | Purpose |
|---|---|---|
| `LLMTestRole` | `Role`, `UseLLM` | Role with LLM calling capability; `llm_send_to` targets the dummy LLM group. |
| `ProposeTestRole` | `LLMTestRole`, `Propose` | Extends `LLMTestRole` with the `Propose` capability. |

---

## Helper Utilities

| Function | Description |
|---|---|
| `install_router_usage(*responses, group=)` | Context manager: configures the router singleton with dummy LLM responses. Restorable by the caller after `with` block exit. |
| `setup_dummy_responses(*responses, group=)` | Same as above but not a context manager — permanent until the next call. |
| `code_block(content, lang)` | Wraps `content` in a fenced code block: ` ```{lang}\n{content}\n``` `. |
| `generic_block(content, lang)` | Wraps `content` in `--- Start of {lang} ---` / `--- End of {lang} ---` delimiters. |
| `make_roles(names, role_cls)` | Creates a list of `Role` instances from a list of names. |
| `make_n_roles(n, role_cls)` | Creates `n` `Role` instances with auto-generated names (`"Role 1"`, `"Role 2"`, …). |
| `setup_dummy_embeddings(*embeddings, group=, model_id=)` | Configures the router with dummy embedding vectors (permanent). |
| `install_dummy_embeddings(*embeddings, group=, model_id=)` | Context manager version of `setup_dummy_embeddings`. |
| `setup_dummy_reranks(*rankings, group=, model_id=)` | Configures the router with dummy reranker ranking tuples (permanent). |
| `install_dummy_reranks(*rankings, group=, model_id=)` | Context manager version of `setup_dummy_reranks`. |

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
|---|---|
| `pad_embeddings(*embeddings, default=, padding=)` | Pads embedding vectors with copies of the default (defaults to last value) for DummyModel safety. |
| `pad_rankings(*rankings, default=, padding=)` | Pads ranking tuples with copies of the default (defaults to last value) for DummyModel safety. |

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

```python
from fabricatio_mock.config import mock_config

# mock_config is a frozen dataclass loaded via CONFIG.load("mock", MockConfig).
# Extend MockConfig in your own code to add mock-specific settings.
```

---

## License

MIT — see [LICENSE](LICENSE)
