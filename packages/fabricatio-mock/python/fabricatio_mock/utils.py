"""Utility module for generating code and generic blocks.

Besides the block helpers, this module seeds the singleton dummy router with
completions, embeddings and reranks for tests, and provides the small bits of
template/config plumbing that test suites keep re-implementing.
"""

import hashlib
import math
import re
import tempfile
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import cast

from fabricatio_core import TEMPLATE_MANAGER, Role, rust
from fabricatio_core.rust import ProviderType

from fabricatio_mock.constants import (
    DUMMY_EMBEDDING_GROUP,
    DUMMY_EMBEDDING_MODEL_ID,
    DUMMY_EVALUATION_GROUP,
    DUMMY_EVALUATION_MODEL_ID,
    DUMMY_LLM_GROUP,
    DUMMY_LLM_MODEL_ID,
    DUMMY_RERANKER_GROUP,
    DUMMY_RERANKER_MODEL_ID,
)
from fabricatio_mock.models.evaluation import EvaluationResponse

_EMBEDDING_SALT_SEPARATOR = "\x00"
"""Separator between salt and text in the digest input of :func:`hash_embedding`."""


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
    rust.ROUTER.add_or_update_dummy_completion_model(group, DUMMY_LLM_MODEL_ID, list(reversed(responses)))


def clear_dummy_responses(group: str = DUMMY_LLM_GROUP) -> None:
    """Empty a dummy completion queue.

    The singleton router has no teardown, so responses seeded by one test leak
    into the next. Clearing leaves the deployment in place but drops every
    queued response, so later calls on the group fail loudly instead of
    silently consuming stale content.

    Args:
        group: Route group to clear. Defaults to DUMMY_LLM_GROUP.
    """
    rust.ROUTER.add_provider(ProviderType.Dummy)
    rust.ROUTER.add_or_update_dummy_completion_model(group, DUMMY_LLM_MODEL_ID, [])


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


def make_roles(names: list[str], role_cls: type[Role] = Role) -> list[Role]:
    """Create a list of Role objects from a list of names.

    Args:
        names (List[str]): A list of names for the roles.
        role_cls (Type[Role]): The Role class to instantiate.

    Returns:
        List[Role]: A list of Role objects with the given names.
    """
    return [role_cls(name=name, description="test") for name in names]


def make_n_roles(n: int, role_cls: type[Role] = Role) -> list[Role]:
    """Create a list of Role objects with a given number of names.

    Args:
        n (int): The number of names.
        role_cls (Type[Role]): The Role class to instantiate.

    Returns:
        List[Role]: A list of Role objects with the given number of names.
    """
    return [role_cls(name=f"Role {i}", description="test") for i in range(1, n + 1)]


def make_test_role(*capabilities: type[object], name: str = "test-role", description: str = "test") -> Role:
    """Build a test role from LLMTestRole plus capability mixins.

    Replaces the per-package pattern of an empty role class and its fixture:

        class DeckRole(LLMTestRole, GenerateDeck): ...
        role = DeckRole(name="deck")

    becomes ``make_test_role(GenerateDeck, name="deck")``. The composed class is
    memoized per capability tuple, so repeated calls reuse a single type.

    Args:
        *capabilities: Capability mixins to compose, in MRO order.
        name: Name given to the role instance.
        description: Description given to the role instance.

    Returns:
        Role: An instance of a class composed from LLMTestRole and the capabilities.
    """
    return _compose_test_role(capabilities)(name=name, description=description)


@cache
def _compose_test_role(capabilities: tuple[type[object], ...]) -> type[Role]:
    """Compose (and memoize) the role class for a capability tuple.

    Args:
        capabilities: Capability mixins to compose, in MRO order.

    Returns:
        type[Role]: The composed role class.
    """
    from fabricatio_mock.models.mock_role import LLMTestRole

    label = "".join(capability.__name__ for capability in capabilities)
    return cast(
        "type[Role]",
        type(f"{label}TestRole", (LLMTestRole, *capabilities), {"__doc__": "Composed test role."}),
    )


def setup_dummy_embeddings(
    *embeddings: list[float],
    group: str = DUMMY_EMBEDDING_GROUP,
    model_id: str = DUMMY_EMBEDDING_MODEL_ID,
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
    *embeddings: list[float],
    group: str = DUMMY_EMBEDDING_GROUP,
    model_id: str = DUMMY_EMBEDDING_MODEL_ID,
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
    *rankings: tuple[int, float],
    group: str = DUMMY_RERANKER_GROUP,
    model_id: str = DUMMY_RERANKER_MODEL_ID,
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
    *rankings: tuple[int, float],
    group: str = DUMMY_RERANKER_GROUP,
    model_id: str = DUMMY_RERANKER_MODEL_ID,
) -> Generator[None, None, None]:
    """Context manager that configures dummy reranker rankings for testing.

    Args:
        *rankings: Ranking tuples of (index, score).
        group: Route group name. Defaults to DUMMY_RERANKER_GROUP.
        model_id: Model identifier string.
    """
    setup_dummy_reranks(*rankings, group=group, model_id=model_id)
    yield


def setup_dummy_evaluations(
    *responses: EvaluationResponse,
    group: str = DUMMY_EVALUATION_GROUP,
    model_id: str = DUMMY_EVALUATION_MODEL_ID,
) -> None:
    """Configure the singleton router with dummy evaluation responses for testing.

    Mutates the singleton ROUTER in-place. The DummyModel uses LIFO (Vec::pop),
    so responses are reversed to preserve FIFO semantics.

    Args:
        *responses: Whole evaluation responses, one per question the router will ask.
        group: Route group name. Defaults to DUMMY_EVALUATION_GROUP.
        model_id: Model identifier string.
    """
    rust.ROUTER.add_provider(ProviderType.Dummy)
    rust.ROUTER.add_or_update_dummy_evaluation_model(
        group, model_id, [response.model_dump_json() for response in reversed(responses)]
    )


@contextmanager
def install_dummy_evaluations(
    *responses: EvaluationResponse,
    group: str = DUMMY_EVALUATION_GROUP,
    model_id: str = DUMMY_EVALUATION_MODEL_ID,
) -> Generator[None, None, None]:
    """Context manager that configures dummy evaluations for testing.

    Args:
        *responses: Whole evaluation responses, one per question the router will ask.
        group: Route group name. Defaults to DUMMY_EVALUATION_GROUP.
        model_id: Model identifier string.
    """
    setup_dummy_evaluations(*responses, group=group, model_id=model_id)
    yield


def hash_embedding(text: str, *, ndim: int = 8, salt: str = "") -> list[float]:
    """Derive a deterministic unit vector from text.

    The same text and salt always yield the same vector, across runs and
    processes, so embedding-dependent assertions stay reproducible without
    hand-written constants.

    Args:
        text: Text to embed.
        ndim: Vector dimensionality.
        salt: Optional namespace mixed into the digest.

    Returns:
        list[float]: A unit-length vector of ndim components.

    Raises:
        ValueError: If ndim is not positive.
    """
    if ndim <= 0:
        raise ValueError("ndim must be positive.")
    digest = hashlib.shake_256(f"{salt}{_EMBEDDING_SALT_SEPARATOR}{text}".encode()).digest(ndim)
    vector = [(byte - 127.5) / 127.5 for byte in digest]
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        uniform = 1.0 / math.sqrt(ndim)
        return [uniform] * ndim
    return [component / norm for component in vector]


def rank_by_overlap(query: str, documents: Sequence[str]) -> list[tuple[int, float]]:
    """Rank document indices by token overlap with the query.

    Scores are the fraction of query tokens found in the document; ties keep
    their original order, so the ranking is fully deterministic.

    Args:
        query: Query text.
        documents: Documents to rank.

    Returns:
        list[tuple[int, float]]: (index, score) pairs sorted by descending score.
    """
    query_tokens = _tokens(query)
    scored = [(index, _overlap(query_tokens, _tokens(document))) for index, document in enumerate(documents)]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored


def setup_fake_embeddings(
    *batches: str | Sequence[str],
    ndim: int = 8,
    salt: str = "",
    group: str = DUMMY_EMBEDDING_GROUP,
    model_id: str = DUMMY_EMBEDDING_MODEL_ID,
) -> None:
    """Seed the dummy embedding model with deterministic vectors.

    Each argument describes one embedding call: a string is a single-text call,
    a sequence is a batch call. Vectors come from :func:`hash_embedding`, so they
    are stable across runs and identifiable by content.

    Args:
        *batches: Texts of each successive embedding call.
        ndim: Vector dimensionality. Defaults to 8.
        salt: Namespace mixed into every vector digest.
        group: Route group to seed. Defaults to DUMMY_EMBEDDING_GROUP.
        model_id: Model identifier to deploy.
    """
    rust.ROUTER.add_provider(ProviderType.Dummy)
    responses = [[hash_embedding(text, ndim=ndim, salt=salt) for text in _as_texts(batch)] for batch in batches]
    rust.ROUTER.add_or_update_dummy_embedding_model(
        group, model_id, [list(response) for response in reversed(responses)]
    )


@contextmanager
def install_fake_embeddings(
    *batches: str | Sequence[str],
    ndim: int = 8,
    salt: str = "",
    group: str = DUMMY_EMBEDDING_GROUP,
    model_id: str = DUMMY_EMBEDDING_MODEL_ID,
) -> Generator[None, None, None]:
    """Context manager that seeds deterministic embeddings.

    Args:
        *batches: Texts of each successive embedding call.
        ndim: Vector dimensionality. Defaults to 8.
        salt: Namespace mixed into every vector digest.
        group: Route group to seed. Defaults to DUMMY_EMBEDDING_GROUP.
        model_id: Model identifier to deploy.
    """
    setup_fake_embeddings(*batches, ndim=ndim, salt=salt, group=group, model_id=model_id)
    yield


def setup_fake_reranks(
    *calls: tuple[str, Sequence[str]],
    group: str = DUMMY_RERANKER_GROUP,
    model_id: str = DUMMY_RERANKER_MODEL_ID,
) -> None:
    """Seed the dummy reranker with overlap-based rankings.

    Each call is a (query, documents) pair; the ranking is computed by
    :func:`rank_by_overlap`, so the returned order is reproducible and derived
    from the declared inputs instead of hand-written index tuples.

    Args:
        *calls: (query, documents) pairs, one per rerank call.
        group: Route group to seed. Defaults to DUMMY_RERANKER_GROUP.
        model_id: Model identifier to deploy.
    """
    rust.ROUTER.add_provider(ProviderType.Dummy)
    rankings = [rank_by_overlap(query, documents) for query, documents in calls]
    rust.ROUTER.add_or_update_dummy_reranker_model(group, model_id, [list(ranking) for ranking in reversed(rankings)])


@contextmanager
def install_fake_reranks(
    *calls: tuple[str, Sequence[str]],
    group: str = DUMMY_RERANKER_GROUP,
    model_id: str = DUMMY_RERANKER_MODEL_ID,
) -> Generator[None, None, None]:
    """Context manager that seeds overlap-based rerankings.

    Args:
        *calls: (query, documents) pairs, one per rerank call.
        group: Route group to seed. Defaults to DUMMY_RERANKER_GROUP.
        model_id: Model identifier to deploy.
    """
    setup_fake_reranks(*calls, group=group, model_id=model_id)
    yield


def stub_template(name: str, body: str, *, directory: str | Path | None = None) -> str:
    r"""Write a stub template and register its directory as a template store.

    The real template is not shipped at test time (or must not be disturbed), so
    tests install a local stub and point a config field at it::

        name = stub_template("test_hashline_diff", "SOURCE:\n{{source}}")
        patched = dataclasses.replace(hashline_edit.diff_config, hashline_diff_template=name)

    The test then installs ``patched`` as ``hashline_edit.diff_config`` for its own
    duration, the way that module's suite already does.

    The store stays registered for the rest of the session: the template manager
    exposes no way to unbind one.

    The stub is written with LF line endings, so its renders are byte-identical
    across platforms.

    Args:
        name: Template name; the file is written as ``<name>.hbs``.
        body: Handlebars source of the stub.
        directory: Store directory. Defaults to a fresh temporary directory.

    Returns:
        str: The template name, ready to assign to a config field.
    """
    store = Path(directory) if directory is not None else Path(tempfile.mkdtemp(prefix="fabricatio-mock-templates-"))
    store.mkdir(parents=True, exist_ok=True)
    (store / f"{name}.hbs").write_text(body, encoding="utf-8", newline="\n")
    TEMPLATE_MANAGER.add_store(store, rediscovery=True)
    return name


def _tokens(text: str) -> set[str]:
    """Split text into lowercase word tokens.

    Args:
        text: Text to tokenize.

    Returns:
        set[str]: The token set.
    """
    return {token for token in re.split(r"\W+", text.lower()) if token}


def _overlap(query_tokens: set[str], document_tokens: set[str]) -> float:
    """Compute the fraction of query tokens present in a document.

    Args:
        query_tokens: Tokens of the query.
        document_tokens: Tokens of the document.

    Returns:
        float: Overlap score in [0, 1].
    """
    if not query_tokens:
        return 0.0
    return len(query_tokens & document_tokens) / len(query_tokens)


def _as_texts(batch: str | Sequence[str]) -> list[str]:
    """Normalize an embedding-call description to a list of texts.

    Args:
        batch: A single text or a sequence of texts.

    Returns:
        list[str]: The texts of one embedding call.
    """
    return [batch] if isinstance(batch, str) else list(batch)
