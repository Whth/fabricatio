# `fabricatio-rag`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-rag)
[![PyPI Version](https://pypi.org/project/fabricatio-rag/)](https://pypi.org/project/fabricatio-rag/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-rag/week)](https://pepy.tech/projects/fabricatio-rag)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-rag)](https://pepy.tech/projects/fabricatio-rag)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

A Python library for Retrieval-Augmented Generation (RAG) capabilities in LLM applications.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[rag]
# or
uv pip install fabricatio[rag]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides tools for:

- Document embedding and vector storage using LanceDB
  This feature uses the LanceDB vector database to store document embeddings. Document embeddings are numerical
  representations of text documents that capture their semantic meaning. The library stores embeddings in LanceDB,
  which provides efficient storage and retrieval with automatic indexing.
- Semantic search and context retrieval
  The semantic search and context retrieval feature allows users to search for relevant documents based on the meaning
  of their queries. It uses nearest-neighbor search on stored embeddings to find documents that are semantically similar
  to the query.
- Reranking with TEI (Text Embeddings Inference) services
  The TEI integration enables document reranking. TEI services provide pre-trained models that can rerank texts
  based on relevance to a query. This allows for state-of-the-art reranking without managing model training locally.
- Database injection workflows
  The database injection workflows handle inserting documents into LanceDB, including vector conversion,
  collection/table creation, data indexing, and error handling.
- Asynchronous RAG execution patterns
  The asynchronous RAG execution patterns allow the library to perform multiple RAG tasks concurrently without blocking
  the main thread.

Built on top of Fabricatio's agent framework with support for asynchronous execution and Rust extensions.

## 🧩 Usage Example

```python
from fabricatio_rag import VectorStoreService, VectorStoreTable, StoreDocument


async def search_knowledge():
    # Initialize database connection (LanceDB URI, e.g. /tmp/lancedb or s3://bucket/path)
    service = await VectorStoreService.connect("data/lancedb")

    # Create a table with embedding dimension 1536 (OpenAI text-embedding-3-small)
    table = await service.create_table("science_papers", ndim=1536)

    # Add documents
    docs = [
        StoreDocument(content="Climate change severely impacts coral reef ecosystems...", vector=[...]),
        StoreDocument(content="Ocean acidification reduces shell thickness in mollusks...", vector=[...]),
    ]
    await table.add_documents(docs)

    # Search for relevant documents
    results = await table.search_document(embedding=[...], limit=3)

    print("Top 3 relevant documents:")
    for result in results:
        print(f"- {result.content[:80]}...")
```

## 📁 Structure

```
fabricatio-rag/
├── actions/          - Data injection workflows
├── capabilities/    - Core RAG functionality
├── models/           - Document models
└── rust.pyi          - Rust extension interfaces
```

## 🔗 Dependencies

Core dependencies:

- `lancedb` - Vector database integration
- `fabricatio-core` - Core interfaces and utilities

Rust extensions:

- LanceDB table management via PyO3 bindings
- TEI reranking via thryd router

## 📄 License

MIT – see [LICENSE](../../LICENSE)
