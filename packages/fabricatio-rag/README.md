# `fabricatio-rag`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-rag)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-rag)](https://pypi.org/project/fabricatio-rag/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-rag/week)](https://pepy.tech/projects/fabricatio-rag)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-rag)](https://pepy.tech/projects/fabricatio-rag)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Abstract framework for building Retrieval-Augmented Generation (RAG) pipelines on top of Fabricatio's
agent architecture. Provides typed base classes, document models, and workflow actions for embedding,
storing, retrieving, and reranking documents.

Requires Python 3.12+.

## Installation

```bash
pip install fabricatio[rag]
# or
uv pip install fabricatio[rag]
```

## Key Components

### RAG Base Class (`RAG`)

Type-parameterized abstract class inheriting `UseEmbedding`, `UseReranker`, and `UseLLM` from `fabricatio-core`.
Defines the core RAG contract that concrete implementations must fulfill:

- `add_document(data, config)` — embed and store documents
- `afetch_document(query, config)` — retrieve documents by semantic similarity
- `arefined_query(question, **kwargs)` — refine user queries via a configurable template before retrieval
- `arank_documents(query, documents, **kwargs)` — rerank previously retrieved documents by relevance

Built-in refinement uses `TEMPLATE_MANAGER.render_template` with the template named in `RagConfig.refined_query_template`
(default: `"built-in/refined_query"`).

```python
from fabricatio_rag.capabilities.rag import RAG, RAGConfigBase
from fabricatio_rag.models.document import StoredDocumentModel, SearchedDocumentModel

class MyRAG(
    RAG[MyStoredDoc, MySearchedDoc, MyAddConfig, MyFetchConfig]
):
    async def add_document(self, data, config=None):
        # embed with self.aembedding(...), store in vector db
        ...

    async def afetch_document(self, query, config=None):
        # embed query, search vector db, return results
        ...
```

### Document Models (`StoredDocumentModel`, `SearchedDocumentModel`)

Generic abstract base classes for document representations.

`StoredDocumentModel[ST]` extends `Base` and `Vectorizable`. Key methods:

- `prepare_insertion(vector) -> ST` — produce a database-ready record from an embedding vector
- `from_txt_files(files, chunk_size, overlap) -> List[Self]` — chunk text files using the Rust-backed `split_into_chunks`, creating one model instance per chunk
- `with_text_chunk(chunk) -> Self` — create an instance from a single text chunk (subclass must implement)

`SearchedDocumentModel[SD]` extends `Base` and `AsPrompt`. Key methods:

- `from_raw(raw) -> Self` — construct from raw database result
- `as_prompt() -> str` — render as prompt text (from `AsPrompt` mixin)

```python
from fabricatio_rag.models.document import StoredDocumentModel, SearchedDocumentModel

class MyStoredDoc(StoredDocumentModel[dict]):
    content: str

    def prepare_insertion(self, vector):
        return {"text": self.content, "vector": vector}

    @classmethod
    def with_text_chunk(cls, chunk):
        return cls(content=chunk)

class MySearchedDoc(SearchedDocumentModel[dict]):
    content: str

    @classmethod
    def from_raw(cls, raw):
        return cls(content=raw["text"])
```

### Workflow Actions (`StoreTextFile`, `StoreDocuments`)

Ready-to-use `Action` subclasses that bridge the Fabricatio workflow engine with RAG storage.

`StoreTextFile` — ingests a list of `Path` objects, chunks them according to `chunk_size` (default 512) and
`chunk_overlap_ratio` (default 0.3), then stores the resulting chunks via `add_document`.

`StoreDocuments` — stores pre-built model instances directly, without any chunking step.

Both accept an optional `store_config` for passing configuration to the underlying `add_document` call.

```python
from fabricatio_rag.actions.db import StoreTextFile

class MyStoreAction(StoreTextFile[MyStoredDoc, MySearchedDoc, MyAddConfig, MyFetchConfig]):
    store_model = MyStoredDoc
    chunk_size = 1024
    chunk_overlap_ratio = 0.2
    store_config = MyAddConfig(collection="docs")
```

### Configuration (`RagConfig`)

Dataclass loaded from Fabricatio's configuration system under the `"rag"` section.

| Field | Default | Description |
|---|---|---|
| `refined_query_template` | `"built-in/refined_query"` | Template name for query refinement |

Access via `fabricatio_rag.config.rag_config`.

## Package Structure

```
fabricatio-rag/
├── python/fabricatio_rag/
│   ├── capabilities/      - RAG abstract base class and config
│   ├── actions/           - StoreTextFile, StoreDocuments workflow actions
│   ├── models/            - StoredDocumentModel, SearchedDocumentModel
│   ├── workflows/         - Workflow definitions (extend here)
│   ├── config.py          - RagConfig dataclass
│   └── __init__.py
└── pyproject.toml
```

## Dependencies

- `fabricatio-core` — LLM routing, embedding, reranking, event system, workflow engine, and Rust text-chunking utilities

## License

MIT — see [LICENSE](../../LICENSE)
