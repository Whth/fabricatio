# `fabricatio-tei`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-tei)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-tei)](https://pypi.org/project/fabricatio-tei/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-tei/week)](https://pepy.tech/projects/fabricatio-tei)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-tei)](https://pepy.tech/projects/fabricatio-tei)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

Integration with [HuggingFace Text Embeddings Inference (TEI)](https://github.com/huggingface/text-embeddings-inference)
for Fabricatio's provider routing system. Register a TEI server as a provider and use it for embedding generation
and document reranking through Fabricatio's standard model interfaces.

Requires Python 3.12+.

## Installation

```bash
pip install fabricatio[tei]
# or
uv pip install fabricatio[tei]
```

## Key Components

### Provider Registration (`add_tei`)

Rust-backed function exposed as `fabricatio_tei.rust.add_tei`. Registers a TEI server as both an embedding
and reranking provider in Fabricatio's global router.

```python
from fabricatio_tei.rust import add_tei

add_tei("my-tei", "http://localhost:8080")
```

After registration, the TEI server is available to any agent or workflow that uses `UseEmbedding` or `UseReranker`
capabilities from `fabricatio-core`. Models created through the router will issue requests to the TEI server's
`/embed` and `/rerank` endpoints.

### `Tei` Capability Mixin

Abstract base class inheriting `UseLLM` from `fabricatio-core`. Provides a `tei()` method placeholder for
building agents that consume TEI services. Extend this class alongside test roles or other capability mixins.

```python
from fabricatio_tei.capabilities.tei import Tei
from fabricatio_mock.models.mock_role import LLMTestRole

class TeiRole(LLMTestRole, Tei):
    """Test role combining LLM testing with TEI capabilities."""
```

### `TeiConfig`

Dataclass loaded from Fabricatio's configuration system under the `"tei"` section. Extend with fields as needed
for your deployment.

```python
from fabricatio_tei.config import tei_config
```

## Supported Endpoints

| Route | Endpoint | Use Case |
|---|---|---|
| `/embed` | POST with `{"inputs": "text"}` | Generate embeddings for text inputs |
| `/rerank` | POST with `{"query": "...", "texts": [...]}` | Rerank documents by relevance to a query |

The TEI provider implements both `EmbeddingModel` and `RerankerModel` from the `thryd` crate, making it
compatible with any Fabricatio workflow that consumes these traits.

## Package Structure

```
fabricatio-tei/
├── python/fabricatio_tei/
│   ├── capabilities/      - Tei abstract base class
│   ├── actions/           - Action definitions
│   ├── models/            - Model definitions
│   ├── workflows/         - Workflow definitions
│   ├── config.py          - TeiConfig dataclass
│   └── __init__.py
├── src/                   - Rust implementation
│   ├── lib.rs             - PyO3 module entry point
│   └── tei.rs             - TEI provider, models, and routes
├── Cargo.toml
└── pyproject.toml
```

## Dependencies

- `fabricatio-core` — router, embedding/reranking interfaces, and configuration system
- `thryd` (Rust) — provider and model abstractions
- `fabricatio-router` (Rust) — global provider registry

## License

This project is licensed under the MIT License.
