# TODO

- [x] RAG package refactor, move rerank and embedding to `thryd`
    - [x] Add Reranker support in `thryd`
    - [x] TEI as `Provider` in thryd (RerankerModel for OpenAI-compat: wontfix — OpenAI doesn't support rerankers)
    - [x] Wire `rerank()` into Router Python class + add `UseReranker` capability
- [x] Convert `fabricatio-rag` to a pure python package
    - [x] Extract lancedb impl into a seperate package
- [ ] `fabricatio-rag` test suite
    - [ ] Unit tests for abstract RAG capability (add_document, afetch_document, refined_query, ranking)
    - [ ] Integration tests with `fabricatio-lancedb` and `fabricatio-milvus` backends
    - [ ] Edge-case tests: empty corpus, duplicate documents, concurrent add/fetch
