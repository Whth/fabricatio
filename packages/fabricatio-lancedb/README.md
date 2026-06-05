# `fabricatio-lancedb`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-lancedb)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-lancedb)](https://pypi.org/project/fabricatio-lancedb/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-lancedb/week)](https://pepy.tech/projects/fabricatio-lancedb)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-lancedb)](https://pepy.tech/projects/fabricatio-lancedb)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

LanceDB vector store backend for Fabricatio RAG. Provides async Rust-backed table
operations — creation, document insertion, vector similarity search, and index
rebuilding — plus Python-side RAG capability mixins and document models.

## Architecture

The package has two layers:

| Layer | Language | Key Types | Purpose |
|-------|----------|-----------|---------|
| Rust (PyO3) | Rust | `VectorStoreService`, `VectorStoreTable`, `StoreDocument`, `SearchedDocument` | High-performance LanceDB table ops with async execution |
| Python | Python | `LancedbRAG`, `LancedbDocumentModel`, `LancedbConfig` | RAG capability, document models, configuration |

The Rust layer manages LanceDB connections and tables. The Python layer
implements the `fabricatio-rag` RAG interface on top of those primitives:
batching embeddings, inserting documents, and searching by vector.

## Installation

```bash
pip install fabricatio[lancedb]
# or
uv pip install fabricatio[lancedb]
```

For all Fabricatio extras:

```bash
pip install fabricatio[full]
```

## Configuration

Configure the LanceDB database URI and default table name via environment,
`.env`, `fabricatio.toml`, or `pyproject.toml`:

```dotenv
FABRICATIO_LANCEDB__DATABASE_URI=./lance.db
FABRICATIO_LANCEDB__DEFAULT_TABLE_NAME=my_docs
```

In `fabricatio.toml`:

```toml
[lancedb]
database_uri = "./lance.db"
default_table_name = "my_docs"
```

The config fields:

| Field | Default | Description |
|-------|---------|-------------|
| `database_uri` | `"./lance.db"` | LanceDB connection URI (local path or S3 `s3://bucket/path`) |
| `default_table_name` | `"default"` | Table name used when none is specified |

Access at runtime:

```python
from fabricatio_lancedb.config import lancedb_config
print(lancedb_config.database_uri)
```

## Usage

### Low-level Rust API

Direct table operations with async Rust execution:

```python
import asyncio
from fabricatio_lancedb.rust import VectorStoreService, VectorStoreTable, StoreDocument

async def main():
    # Connect to LanceDB
    service = await VectorStoreService.connect("./lance.db")

    # Create a table for 1536-dim embeddings (OpenAI text-embedding-3-small)
    table = await service.create_table("my_table", ndim=1536)

    # Add documents
    docs = [
        StoreDocument(
            content="LanceDB is a fast, open-source vector database.",
            vector=[0.1] * 1536,
        ),
        StoreDocument.with_metadata(
            content="Fabricatio is an LLM application framework.",
            vector=[0.2] * 1536,
            metadata={"source": "docs", "version": "1.0"},
        ),
    ]
    ids = await table.add_documents(docs)
    print(f"Inserted: {ids}")

    # Search by embedding
    results = await table.search_document(embedding=[0.15] * 1536, limit=5)
    for r in results:
        print(f"{r.id}: {r.content[:60]}...")
        print(f"  metadata: {r.access_metadata()}")

    # Rebuild the index after bulk inserts with rebuild_index=False
    await table.rebuild_index()

asyncio.run(main())
```

### RAG capability (high-level)

Integrate with Fabricatio's RAG system using the `LancedbRAG` mixin:

```python
from fabricatio_lancedb.capabilities.lancedb import LancedbRAG, LancedbAddRAGConfig, LancedbFetchRAGConfig
from fabricatio_lancedb.models.lancedb import LancedbDocumentModel

class MyDoc(LancedbDocumentModel):
    """Custom document with additional fields."""
    title: str = ""

class MyRAGRole(SomeBaseRole, LancedbRAG[MyDoc, LancedbAddRAGConfig, LancedbFetchRAGConfig[MyDoc]]):
    pass

async def run():
    role = MyRAGRole()
    # Add a document — handles embedding batching internally
    await role.add_document(
        MyDoc(content="Semantic search with LanceDB and Fabricatio.", title="Intro"),
        config=LancedbAddRAGConfig(table_name="docs", embedding_batch_size=20),
    )
    # Fetch relevant documents
    results = await role.afetch_document(
        "how does semantic search work",
        config=LancedbFetchRAGConfig(document_model=MyDoc, limit=10),
    )
    for doc in results:
        print(f"[{doc.title}] {doc.content}")
```

### Cached service helper

Reuse connections across calls:

```python
from fabricatio_lancedb.inited_service import get_service

service = await get_service("s3://my-bucket/lancedb")
table = await service.open_table("production_docs")
```

## API Reference

### Rust layer (`fabricatio_lancedb.rust`)

#### VectorStoreService

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `connect` | `(uri: str) -> Awaitable[Self]` | `VectorStoreService` | Static — connect to a LanceDB instance |
| `create_table` | `(table_name: str, ndim: int) -> Awaitable[VectorStoreTable]` | `VectorStoreTable` | Create a new table with the given vector dimension |
| `open_table` | `(table_name: str) -> Awaitable[VectorStoreTable]` | `VectorStoreTable` | Open an existing table |
| `create_or_open_table` | `(table_name: str, ndim: int) -> Awaitable[VectorStoreTable]` | `VectorStoreTable` | Create if absent, otherwise open |

#### VectorStoreTable

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `add_documents` | `(documents: list[StoreDocument], rebuild_index: bool = True) -> Awaitable[list[str]]` | Document IDs | Insert documents; set `rebuild_index=False` for bulk inserts |
| `search_document` | `(embedding: list[float], limit: int) -> Awaitable[list[SearchedDocument]]` | Search results | Nearest-neighbor vector search |
| `rebuild_index` | `() -> Awaitable[None]` | None | Rebuild the vector index (no-op if <256 rows) |

#### StoreDocument

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Document text content |
| `vector` | `list[float]` | Dense embedding vector |
| `metadata` | `str \| None` | Optional JSON-serialized metadata |

Static constructor `StoreDocument.with_metadata(content, vector, metadata: dict)` serializes
the metadata dict to JSON.

#### SearchedDocument

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | UUID document identifier |
| `content` | `str` | Matched document text |
| `timestamp` | `int` | Microsecond-precision timestamp |
| `metadata` | `str \| None` | Raw JSON metadata string |

Method `access_metadata() -> dict` parses the JSON metadata into a Python dict.

### Python layer

#### LancedbRAG

Extends `RAG` from `fabricatio-rag` with LanceDB storage.

| Method | Description |
|--------|-------------|
| `add_document(data, config)` | Vectorize and insert one or more documents |
| `afetch_document(query, config)` | Vectorize a query string and return matching documents |
| `rebuild_index(table_name?)` | Rebuild the vector index on a table |

#### LancedbAddRAGConfig

Dataclass config for `add_document`:

| Field | Default | Description |
|-------|---------|-------------|
| `table_name` | `lancedb_config.default_table_name` | Target table |
| `embedding_batch_size` | `10` | Documents per embedding batch |
| `embedding_parallel_size` | `10` | Max concurrent embedding calls |
| `rebuild_index` | `False` | Rebuild index after insertion |

#### LancedbFetchRAGConfig

Dataclass config for `afetch_document`:

| Field | Default | Description |
|-------|---------|-------------|
| `table_name` | `lancedb_config.default_table_name` | Source table |
| `document_model` | `None` (required) | Document model class for deserialization |
| `limit` | `15` | Max results returned |

#### LancedbDocumentModel

Extends `StoredDocumentModel` and `SearchedDocumentModel`. Fields: `content` (str), `metadata` (dict | None).

| Method | Description |
|--------|-------------|
| `prepare_insertion(vector) -> StoreDocument` | Build a Rust `StoreDocument` ready for insertion |
| `from_raw(raw: SearchedDocument) -> Self` | Deserialize a Rust `SearchedDocument` |
| `with_text_chunk(chunk: str) -> Self` | Create from a plain text chunk |

## Schema

Each LanceDB table uses this Arrow schema:

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `item` | `Utf8` | no | Primary key (UUID v7) |
| `timestamp` | `Time64(µs)` | no | Insertion timestamp |
| `vector` | `FixedSizeList(Float32, ndim)` | no | Embedding vector |
| `content` | `Utf8` | no | Document text |
| `metadata` | `Utf8` | yes | JSON-serialized metadata |

## Dependencies

- `fabricatio-core` — core interfaces and configuration
- `fabricatio-rag` — base RAG abstractions (`RAG`, document models)
- `more-itertools` — chunked iteration for batch processing
- `async-lru` — async LRU caching

Rust dependencies (via PyO3): `lancedb`, `arrow`, `pyo3`, `tokio`.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE).
