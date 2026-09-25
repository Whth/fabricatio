"""Shared constants: dummy router group names and the model identifiers deployed to them."""

DUMMY_LLM_GROUP: str = "llm"
"""Default router group name used by mock LLM roles and test utilities."""

DUMMY_EMBEDDING_GROUP: str = "embedding"
"""Default router group name used by mock embedding models and test utilities."""

DUMMY_RERANKER_GROUP: str = "reranker"
"""Default router group name used by mock reranker models and test utilities."""

DUMMY_EVALUATION_GROUP: str = "evaluation"
"""Default router group name used by mock evaluation models and test utilities."""

DUMMY_LLM_MODEL_ID: str = "dummy/test-model"
"""Model identifier deployed to ``DUMMY_LLM_GROUP`` by the completion seeding helpers."""

DUMMY_EMBEDDING_MODEL_ID: str = "dummy/test-embedding-model"
"""Model identifier deployed to ``DUMMY_EMBEDDING_GROUP`` by the embedding seeding helpers."""

DUMMY_RERANKER_MODEL_ID: str = "dummy/test-reranker-model"
"""Model identifier deployed to ``DUMMY_RERANKER_GROUP`` by the reranker seeding helpers."""

DUMMY_EVALUATION_MODEL_ID: str = "dummy/test-evaluation-model"
"""Model identifier deployed to ``DUMMY_EVALUATION_GROUP`` by the evaluation seeding helpers."""

__all__ = [
    "DUMMY_EMBEDDING_GROUP",
    "DUMMY_EMBEDDING_MODEL_ID",
    "DUMMY_EVALUATION_GROUP",
    "DUMMY_EVALUATION_MODEL_ID",
    "DUMMY_LLM_GROUP",
    "DUMMY_LLM_MODEL_ID",
    "DUMMY_RERANKER_GROUP",
    "DUMMY_RERANKER_MODEL_ID",
]
