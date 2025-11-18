# `fabricatio-rag`

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

- Document embedding and vector storage using Milvus
This feature uses the Milvus vector database to store document embeddings. Document embeddings are numerical representations of text documents that capture their semantic meaning. The library first converts text documents into embeddings using appropriate embedding models. These embeddings are then stored in Milvus, which provides efficient storage and retrieval capabilities. For example, it can handle large - scale document collections and perform fast similarity searches.
- Semantic search and context retrieval
The semantic search and context retrieval feature allows users to search for relevant documents based on the meaning of their queries. It uses the stored document embeddings in Milvus to find documents that are semantically similar to the query. This is more powerful than traditional keyword - based search as it can understand the intent behind the query. For example, if a user searches for "effects of pollution on wildlife", it can retrieve documents that discuss related concepts even if the exact keywords are not present.
- Integration with TEI (Text Embeddings Inference) services
The integration with TEI services enables the generation of text embeddings. TEI services provide pre - trained models that can convert text into embeddings. The library can send text data to the TEI service and receive the corresponding embeddings. This allows for the use of state - of - the - art embedding models without having to manage the model training and inference process locally.
- Database injection workflows
The database injection workflows are responsible for inserting new documents into the Milvus database. It takes care of the process of converting the documents into embeddings, and then inserting them into the appropriate collections in Milvus. This includes handling tasks such as collection creation, data indexing, and error handling.
- Asynchronous RAG execution patterns
The asynchronous RAG execution patterns allow the library to perform multiple RAG tasks concurrently without blocking the main thread. This is useful for improving the performance and responsiveness of the application. For example, it can handle multiple user queries simultaneously, reducing the overall response time.

Built on top of Fabricatio's agent framework with support for asynchronous execution and Rust extensions.

## 🧩 Usage Example

```python
from fabricatio_rag.capabilities.rag import RAG
The `RAG` class is the core component of the library. It provides methods for performing retrieval - augmented generation tasks. It interacts with the Milvus database for document retrieval and uses the generated embeddings to augment the generation process.
from fabricatio_rag.models.rag import MilvusDataBase
The `MilvusDataBase` class represents the connection to the Milvus vector database. It provides methods for creating collections, inserting documents, and performing searches. It abstracts the low - level details of working with Milvus, making it easier to use in the application.


async def search_knowledge():
    # Initialize database connection
    db = MilvusDataBase(collection_name="science_papers")
    This line initializes a connection to the Milvus database with a specific collection named "science_papers". The collection is where the document embeddings will be stored and retrieved from.

    # Initialize RAG capability
    rag = RAG(db)
    This line creates an instance of the `RAG` class, passing in the `MilvusDataBase` object. This allows the `RAG` class to interact with the Milvus database for document retrieval.

    # Search for relevant information
    results = await rag.retrieve("climate change impact on coral reefs", limit=3)
    The `retrieve` method of the `RAG` class is used to perform a semantic search in the Milvus database. It takes a query string and a limit as parameters. In this example, it searches for documents related to "climate change impact on coral reefs" and returns the top 3 relevant documents.

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