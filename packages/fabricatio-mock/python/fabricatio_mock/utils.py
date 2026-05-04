"""Utility module for generating code and generic blocks.

Provides functions to generate fenced code blocks and generic content blocks.
"""

from contextlib import contextmanager
from typing import Generator, List, Type

from fabricatio_core import Role, rust
from fabricatio_core.rust import ProviderType

from fabricatio_mock import DUMMY_EMBEDDING_GROUP, DUMMY_LLM_GROUP, DUMMY_RERANKER_GROUP


def code_block(content: str, lang: str = "json") -> str:
    """Generate a code block."""
    return f"```{lang}\n{content}\n```"


def generic_block(content: str, lang: str = "String") -> str:
    """Generate a generic block."""
    return f"--- Start of {lang} ---\n{content}\n--- End of {lang} ---"


def setup_dummy_responses(*responses: str, group: str = DUMMY_LLM_GROUP) -> None:
    """Configure the singleton router with dummy responses for testing.

    Mutates the singleton ROUTER in-place. The DummyModel uses LIFO (Vec::pop),
    so responses are reversed to preserve FIFO semantics.

    Args:
        *responses: Pre-formatted response strings (e.g. code_block, generic_block).
        group: Route group name. Defaults to match LLMTestRole.llm_send_to.
    """
    rust.ROUTER.add_provider(ProviderType.Dummy)
    rust.ROUTER.add_or_update_dummy_completion_model(group, "dummy/test-model", list(reversed(responses)))


@contextmanager
def install_router_usage(*responses: str, group: str = DUMMY_LLM_GROUP) -> Generator[None, None, None]:
    """Configure the singleton router with dummy responses for testing.

    Mutates the singleton ROUTER in-place. The DummyModel uses LIFO (Vec::pop),
    so responses are reversed to preserve FIFO semantics.

    Args:
        *responses: Pre-formatted response strings (e.g. code_block, generic_block).
        group: Route group name. Defaults to match LLMTestRole.llm_send_to.
    """
    setup_dummy_responses(*responses, group=group)
    yield


def make_roles(names: List[str], role_cls: Type[Role] = Role) -> List[Role]:
    """Create a list of Role objects from a list of names.

    Args:
        names (List[str]): A list of names for the roles.
        role_cls (Type[Role]): The Role class to instantiate.

    Returns:
        List[Role]: A list of Role objects with the given names.
    """
    return [role_cls(name=name, description="test") for name in names]


def make_n_roles(n: int, role_cls: Type[Role] = Role) -> List[Role]:
    """Create a list of Role objects with a given number of names.

    Args:
        n (int): The number of names.
        role_cls (Type[Role]): The Role class to instantiate.

    Returns:
        List[Role]: A list of Role objects with the given number of names.
    """
    return [role_cls(name=f"Role {i}", description="test") for i in range(1, n + 1)]


def setup_dummy_embeddings(
    *embeddings: list[float], group: str = DUMMY_EMBEDDING_GROUP, model_id: str = "dummy/test-embedding-model"
) -> None:
    """Configure the singleton router with dummy embeddings for testing.

    Mutates the singleton ROUTER in-place. The DummyModel uses LIFO (Vec::pop),
    so embeddings are reversed to preserve FIFO semantics.

    Args:
        *embeddings: Embedding vectors (each a list of floats).
        group: Route group name. Defaults to DUMMY_EMBEDDING_GROUP.
        model_id: Model identifier string.
    """
    rust.ROUTER.add_provider(ProviderType.Dummy)
    # Each embedding is a list[float]; wrap in a list to form the batch type (Vec<Embeddings>)
    rust.ROUTER.add_or_update_dummy_embedding_model(group, model_id, [[e] for e in reversed(embeddings)])


@contextmanager
def install_dummy_embeddings(
    *embeddings: list[float], group: str = DUMMY_EMBEDDING_GROUP, model_id: str = "dummy/test-embedding-model"
) -> Generator[None, None, None]:
    """Context manager that configures dummy embeddings for testing.

    Args:
        *embeddings: Embedding vectors (each a list of floats).
        group: Route group name. Defaults to DUMMY_EMBEDDING_GROUP.
        model_id: Model identifier string.
    """
    setup_dummy_embeddings(*embeddings, group=group, model_id=model_id)
    yield


def setup_dummy_reranks(
    *rankings: tuple[int, float], group: str = DUMMY_RERANKER_GROUP, model_id: str = "dummy/test-reranker-model"
) -> None:
    """Configure the singleton router with dummy reranker rankings for testing.

    Mutates the singleton ROUTER in-place. The DummyModel uses LIFO (Vec::pop),
    so rankings are reversed to preserve FIFO semantics.

    Args:
        *rankings: Ranking tuples of (index, score).
        group: Route group name. Defaults to DUMMY_RERANKER_GROUP.
        model_id: Model identifier string.
    """
    rust.ROUTER.add_provider(ProviderType.Dummy)
    # Each ranking tuple is wrapped in a list to form the batch type (Vec<Ranking>)
    rust.ROUTER.add_or_update_dummy_reranker_model(group, model_id, [[r] for r in reversed(rankings)])


@contextmanager
def install_dummy_reranks(
    *rankings: tuple[int, float], group: str = DUMMY_RERANKER_GROUP, model_id: str = "dummy/test-reranker-model"
) -> Generator[None, None, None]:
    """Context manager that configures dummy reranker rankings for testing.

    Args:
        *rankings: Ranking tuples of (index, score).
        group: Route group name. Defaults to DUMMY_RERANKER_GROUP.
        model_id: Model identifier string.
    """
    setup_dummy_reranks(*rankings, group=group, model_id=model_id)
    yield
