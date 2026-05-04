# `fabricatio-mock`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-mock)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-mock)](https://pypi.org/project/fabricatio-mock/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-mock/week)](https://pepy.tech/projects/fabricatio-mock)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-mock)](https://pepy.tech/projects/fabricatio-mock)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Test utilities and mock implementations for fabricatio. Provides configurable dummy LLM responses
so you can test agent workflows without real API calls.

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
    # The default value is appended automatically for safety.
    with install_router_usage(*return_router_usage("Hello", "World")):
        result = await some_llm_call(question="greet")
        assert result == "Hello"

        result = await some_llm_call(question="farewell")
        assert result == "World"
```

### Important: unique question strings

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
| `return_router_usage(*values, default=)` | Plain string responses |
| `return_json_router_usage(*jsons, default=)` | Wraps each in a JSON code block |
| `return_code_router_usage(*codes, lang=, default=)` | Wraps each in a fenced code block |
| `return_python_router_usage(*codes, default=)` | Shorthand for `lang="python"` |
| `return_json_obj_router_usage(*objs, default=)` | Serializes objects with `orjson` then wraps in JSON block |
| `return_model_json_router_usage(*models, default=)` | Serializes Pydantic models then wraps in JSON block |
| `return_generic_router_usage(*strings, lang=, default=)` | Wraps each in a generic delimiter block |
| `return_mixed_router_usage(*values, default=)` | Accepts `Value` dataclass for mixed-type responses |

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

Type options: `"model"`, `"json"`, `"python"`, `"generic"`, `"raw"`.

---

## Test Roles

Pre-configured roles for testing LLM and Propose capabilities:

```python
from fabricatio_mock.models.mock_role import LLMTestRole, ProposeTestRole

role = LLMTestRole(name="tester")
    # llm_send_to="openai/gpt-3.5-turbo"
    # llm_api_endpoint="https://api.openai.com/v1"
    # llm_api_key=SecretStr("sk-123456789")
```

---

## Helper Utilities

| Function | Description |
|---|---|
| `install_router_usage(*responses, group=)` | Context manager: configures the router singleton with dummy responses |
| `setup_dummy_responses(*responses, group=)` | Same as above but not a context manager (permanent until next call) |
| `code_block(content, lang)` | Wraps content in a fenced code block |
| `generic_block(content, lang)` | Wraps content in `--- Start/End of ... ---` delimiters |
| `make_roles(names, role_cls)` | Creates a list of Role instances from names |
| `make_n_roles(n, role_cls)` | Creates n Role instances with auto-generated names |
| `setup_dummy_embeddings(*embeddings, group=, model_id=)` | Configures router with dummy embedding vectors |
| `install_dummy_embeddings(*embeddings, group=, model_id=)` | Context manager version of the above |
| `setup_dummy_reranks(*rankings, group=, model_id=)` | Configures router with dummy reranker ranking tuples |
| `install_dummy_reranks(*rankings, group=, model_id=)` | Context manager version of the above |

---

## How It Works

fabricatio delegates LLM calls to a Rust-side singleton router (`rust.ROUTER`).
`install_router_usage` mutates this singleton in-place by:

1. Registering a `DummyProvider`
2. Deploying a `DummyModel` with the given responses to the `"openai/gpt-3.5-turbo"` route

Responses are popped from the model's queue in LIFO order internally; the builder functions
reverse them before storing so callers get FIFO semantics.

Because the router is a shared `Arc`, all code paths that call through `router_usage.ask()`
see the injected responses automatically.

---

## Legacy API

The older `install_router` + `return_string` API patches `rust.ROUTER` at the Python level.
This no longer intercepts calls made through `UseLLM` (which delegates to `rust.router_usage.ask()`).

These functions are kept for backward compatibility but should not be used for new tests:

- `install_router(router)` — Python-level `unittest.mock.patch` on `rust.ROUTER`
- `return_string(*values)` — returns a mock `Router` object
- `return_json_string`, `return_python_string`, `return_code_string`, `return_generic_string`, etc.

---

## License

MIT - see [LICENSE](../../LICENSE)

---

## Embedding & Rerank Mocking

In addition to completion mocking, `fabricatio-mock` supports embedding and reranker mocking.

### Constants

| Constant | Default Value | Description |
|---|---|---|
| `DUMMY_EMBEDDING_GROUP` | `"embedding"` | Default router group for mock embedding models |
| `DUMMY_RERANKER_GROUP` | `"reranker"` | Default router group for mock reranker models |

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
| `pad_embeddings(*embeddings, default=, padding=)` | Pads embedding vectors with copies of the default for DummyModel safety |
| `pad_rankings(*rankings, default=, padding=)` | Pads ranking tuples with copies of the default for DummyModel safety |