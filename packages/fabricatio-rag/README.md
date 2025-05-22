# `fabricatio-rag`

A Python library for Retrieval-Augmented Generation (RAG) capabilities in LLM applications.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[rag]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides tools for:

- Document embedding and vector storage using Milvus
- Semantic search and context retrieval
- Integration with TEI (Text Embeddings Inference) services
- Database injection workflows
- Asynchronous RAG execution patterns

Built on top of Fabricatio's agent framework with support for asynchronous execution and Rust extensions.

## 🧩 Usage Example

```python
from fabricatio_rag.capabilities.rag import RAG
from fabricatio_rag.models.rag import MilvusDataBase


async def search_knowledge():
    # Initialize database connection
    db = MilvusDataBase(collection_name="science_papers")

    # Initialize RAG capability
    rag = RAG(db)

    # Search for relevant information
    results = await rag.retrieve("climate change impact on coral reefs", limit=3)

    print("Top 3 relevant documents:")
    for result in results:
        print(f"- {result['title']}")
        print(f"  Relevance: {result['score']:.2f}")
        print(f"  Snippet: {result['text'][:150]}...")
```

## 📁 Structure

```
fabricatio-rag/
├── actions/          - Data injection workflows
├── capabilities/     - Core RAG functionality
├── models/           - Database and query models
├── proto/            - TEI service definitions
└── rust.pyi          - Rust extension interfaces
```

## 🔗 Dependencies

Core dependencies:

- `pymilvus>=2.5.4` - Vector database integration
- `fabricatio-core` - Core interfaces and utilities

Rust extensions:

- TEI client bindings
- Protobuf definitions for gRPC communication

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)