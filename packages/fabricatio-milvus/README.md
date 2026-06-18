# `fabricatio-milvus`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-milvus)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-milvus)](https://pypi.org/project/fabricatio-milvus/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-milvus/week)](https://pepy.tech/projects/fabricatio-milvus)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-milvus)](https://pepy.tech/projects/fabricatio-milvus)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Milvus vector database integration for Fabricatio — store, search, and retrieve document embeddings with the Fabricatio RAG framework.

## Installation

```bash
pip install fabricatio[milvus]
```

Or install all Fabricatio components:

```bash
pip install fabricatio[full]
```

## Overview

`fabricatio-milvus` extends Fabricatio's RAG (Retrieval-Augmented Generation) system with a Milvus vector database backend. It provides:

- Pydantic-based document models that auto-generate Milvus collection schemas from field type annotations.
- A `MilvusRAG` capability class implementing the `add_document`/`afetch_document`/`aretrieve` contract backed by `pymilvus`.
- Ready-to-use `Action` subclasses (`InjectToDB`, `MilvusRAGTalk`) for building agent pipelines.

## Configuration

Milvus settings are loaded from the Fabricatio config system under the `milvus` namespace:

```python
from fabricatio_milvus.config import milvus_config

# milvus_config.milvus_uri       → str | None
# milvus_config.milvus_timeout   → float | None
# milvus_config.milvus_token     → SecretStr | None
# milvus_config.milvus_dimensions → int | None
```

These can also be set per-instance via `MilvusScopedConfig` (pydantic model with the same fields).

## Key Components

### Models — `fabricatio_milvus.models`

| Class | Description |
|---|---|
| `MilvusDataBase[ST]` | Abstract base combining `StoredDocumentModel` and `SearchedDocumentModel`. Generates Milvus `CollectionSchema` from Pydantic fields (`int` → `INT64`, `str` → `VARCHAR`, `float` → `DOUBLE`, `list[str]` → `ARRAY[VARCHAR]`, `JsonValue` → `JSON`). Default index type `FLAT`, metric type `COSINE`. |
| `MilvusClassicModel[SD]` | Minimal concrete model with a single `text: str` field. |
| `MilvusScopedConfig` | Per-instance override for Milvus connection parameters (uri, token, timeout, dimensions). |

### Capabilities — `fabricatio_milvus.capabilities`

| Class / Function | Description |
|---|---|
| `create_client(uri, token, timeout)` | Cached factory returning a `pymilvus.MilvusClient`. |
| `AddConfig` | Configuration for `add_document`: `collection_name`, `flush`. |
| `FetchConfig[D]` | Configuration for `afetch_document`: `document_model`, `collection_name`, `similarity_threshold` (default 0.37), `result_per_query` (default 10), `tei_endpoint`, `reranker_threshold`, `filter_expr`. |
| `MilvusRAG[D, AC, FC]` | Core RAG class backed by Milvus. Inherits from `RAG`, `MilvusScopedConfig`, `UseEmbedding`, `UseReranker`, `UseLLM`. |

**`MilvusRAG` methods:**

- `client` — property returning the `MilvusClient`, eagerly created on construction from config.
- `add_document(data, config)` — vectorize documents and insert into a collection. Creates the collection if it doesn't exist.
- `afetch_document(query, config)` — vectorize query strings, search Milvus, deduplicate by ID, sort by distance descending, and deserialize into typed document models.
- `aretrieve(query, document_model, ...)` — convenience wrapper that builds a `FetchConfig` and calls `afetch_document`.

### Actions — `fabricatio_milvus.actions`

| Action | Description |
|---|---|
| `InjectToDB` | Action that injects `MilvusDataBase` instances into a Milvus collection. Automatically creates the collection with the correct schema and index if needed. Supports `override_inject` to drop and recreate. |
| `MilvusRAGTalk` | Interactive RAG conversation loop. Queries Milvus with user input, retrieves relevant documents, augments the LLM prompt, and returns generated responses. Runs until the user exits. |

## Usage Example

```python
from fabricatio_milvus.actions.rag import InjectToDB
from fabricatio_milvus.models.milvus import MilvusClassicModel

# Create document models
docs = [
    MilvusClassicModel(text="Fabricatio is a Python library for building LLM applications."),
    MilvusClassicModel(text="Milvus is an open-source vector database."),
]

# Inject into Milvus
action = InjectToDB(
    collection_name="my_knowledge_base",
    milvus_uri="http://localhost:19530",
)
await action.execute(to_inject=docs)
```

## Dependencies

- `fabricatio-core` — core interfaces, config, and utilities
- `fabricatio-rag` — RAG abstractions (`RAG`, document models)
- `pymilvus` (≥2.5.4) — Milvus Python SDK
- `pydantic` (≥2.7.1) — data validation and schema generation
- `more-itertools` (≥10.8.0) — additional itertools

## License

MIT
