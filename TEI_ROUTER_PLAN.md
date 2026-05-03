# TEI Router Integration — Design Decisions

## Context
Porting TEI (Text Embeddings Inference) provider from deprecated gRPC to thryd-based implementation.

**Files:**
- `packages/fabricatio-rag/src/tei.rs` — TEI provider + model implementation (done)
- `packages/fabricatio-core/src/router.rs` — Router with `embedding/completion/reranker` routers (needs update)

**Goal:** Add TEI provider and models to the Router so Python can call `router.embedding(...)` / `router.reranker(...)` with TEI-backed models.

---

## 1. Which routers should receive TEI provider?

| Option | Routers | Use Case |
|--------|---------|----------|
| **A** | Reranker only | Default — TEI reranking is the primary RAG use case |
| **B** | Embedding + Reranker | TEI supports both `/embed` and `/rerank` endpoints |
| **C** | All three | Future-proofing (completion unlikely but possible) |

**Implication:** `Router` already has `reranker_router` field but no public API to use it.

---

## 2. How should the API be exposed to Python?

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A** | New method `add_tei_provider(url, model_id)` | Clean, self-contained | Duplicates existing `add_provider` pattern |
| **B** | Expose `reranker_router` getter | Full flexibility | Leaks internal structure |
| **C** | `add_reranker_model()` method | Consistent with existing `add_*_model()` pattern | Missing `add_reranker_provider()` counterpart |

**Current pattern in Router:**
```python
router.add_provider(ProviderType.OpenAICompatible, name="...", api_key=..., endpoint=...)
router.add_completion_model("default", "openai/gpt-4")
router.add_embedding_model("embed", "openai/text-embedding-3-small")
```

---

## 3. RerankerTag vs EmbeddingTag for TEI model?

TEI's `TEIModel` implements **both** `EmbeddingModel` and `RerankerModel`.

| Option | Behavior |
|--------|----------|
| **A** | Single TEI deployment → both `embedding_router` + `reranker_router` |
| **B** | Separate deployments: `tei/embed-model` for embedding, `tei/rerank-model` for reranker |
| **C** | Config-driven: user specifies which router(s) to add to |

---

## Status

- [x] Decision 2: Python API style — **C**: `add_reranker_model()` method, consistent with `add_completion_model()` and `add_embedding_model()`
- [ ] Decision 1: Which routers receive TEI
- [ ] Decision 3: Single vs dual model deployment