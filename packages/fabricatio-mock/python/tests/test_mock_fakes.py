"""Tests for the deterministic embedding and reranker fakes."""

import math
from uuid import uuid4

import pytest
from fabricatio_core import rust
from fabricatio_mock.utils import (
    hash_embedding,
    install_fake_embeddings,
    install_fake_reranks,
    rank_by_overlap,
)


class TestHashEmbedding:
    """hash_embedding derives stable unit vectors from text."""

    def test_is_deterministic(self) -> None:
        """Identical inputs yield identical vectors."""
        assert hash_embedding("alpha", ndim=6) == hash_embedding("alpha", ndim=6)

    def test_is_unit_length(self) -> None:
        """The vector is normalized to unit length."""
        vector = hash_embedding("alpha", ndim=16)
        norm = math.sqrt(sum(component * component for component in vector))

        assert math.isclose(norm, 1.0)

    def test_distinguishes_texts_and_salts(self) -> None:
        """Different text or salt yields a different vector."""
        assert hash_embedding("alpha") != hash_embedding("beta")
        assert hash_embedding("alpha") != hash_embedding("alpha", salt="other")

    def test_rejects_non_positive_ndim(self) -> None:
        """A non-positive dimensionality is rejected."""
        with pytest.raises(ValueError, match="ndim must be positive"):
            hash_embedding("alpha", ndim=0)


class TestRankByOverlap:
    """rank_by_overlap sorts documents by query-token coverage."""

    def test_orders_by_overlap(self) -> None:
        """The document sharing more query tokens comes first."""
        ranking = rank_by_overlap("rust book", ["python guide", "rust book review"])

        assert [index for index, _ in ranking] == [1, 0]
        assert ranking[0][1] > ranking[1][1]

    def test_keeps_index_order_on_ties(self) -> None:
        """Equal scores keep their original order."""
        ranking = rank_by_overlap("rust", ["rust", "rust"])

        assert [index for index, _ in ranking] == [0, 1]

    def test_empty_documents(self) -> None:
        """No documents yields an empty ranking."""
        assert rank_by_overlap("rust", []) == []


class TestInstallFakeEmbeddings:
    """install_fake_embeddings seeds hash vectors through the router."""

    async def test_batch_call_returns_declared_vectors(self) -> None:
        """A batch call receives one hash vector per text.

        The texts carry a run-unique token: the router caches embeddings per
        text hash in a store shared with production runs.
        """
        texts = [f"alpha-{uuid4().hex}", f"beta-{uuid4().hex}"]

        with install_fake_embeddings(texts, ndim=4):
            vectors = await rust.ROUTER.embedding("embedding", texts, 4)

        assert len(vectors) == 2
        assert vectors[0] == pytest.approx(hash_embedding(texts[0], ndim=4), rel=1e-6)
        assert vectors[1] == pytest.approx(hash_embedding(texts[1], ndim=4), rel=1e-6)

    async def test_single_text_call(self) -> None:
        """A string argument describes a single-text call."""
        text = f"solo-{uuid4().hex}"

        with install_fake_embeddings(text, ndim=4):
            vectors = await rust.ROUTER.embedding("embedding", [text], 4)

        assert vectors[0] == pytest.approx(hash_embedding(text, ndim=4), rel=1e-6)

    async def test_salt_changes_the_vector(self) -> None:
        """The salt participates in the digest, so vectors differ per namespace."""
        text = f"salted-{uuid4().hex}"

        with install_fake_embeddings([text], ndim=4, salt="one"):
            first = (await rust.ROUTER.embedding("embedding", [text], 4))[0]

        assert first == pytest.approx(hash_embedding(text, ndim=4, salt="one"), rel=1e-6)
        assert first != pytest.approx(hash_embedding(text, ndim=4, salt="two"), rel=1e-6)


class TestInstallFakeReranks:
    """install_fake_reranks ranks declared documents by overlap."""

    async def test_ranking_follows_overlap(self) -> None:
        """The document containing the query token ranks first."""
        token = uuid4().hex
        query = f"rust {token}"
        documents = [f"python guide {token}", f"rust handbook {token}"]

        with install_fake_reranks((query, documents)):
            ranking = await rust.ROUTER.rerank("reranker", query, documents)

        assert [index for index, _ in ranking] == [1, 0]
        assert ranking[0][1] == pytest.approx(1.0)
