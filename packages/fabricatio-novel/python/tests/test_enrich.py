"""Integration tests for fabricatio-novel enrich capability and StoreEnrichedTexts action.

Exercises the LLM-driven enrichment pipeline that backs `StoreEnrichedTexts`:

- `EnrichChunkTextNovel` is a thin subclass — `enrich()` must still work end-to-end
  via `ProposeTestRole` + `install_router_usage`.
- `_qa_pairs_to_chunks` must flatten `EnrichmentResult.qa_pairs` deterministically.
- `StoreEnrichedTexts._execute` must read files, call `enrich`, and dispatch the
  flattened chunks to `add_document`. We mock `add_document` + `rebuild_index`
  on the live instance so the LanceDB runtime is not exercised.
"""

from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, patch

import pytest
from fabricatio_mock.models.mock_role import ProposeTestRole
from fabricatio_mock.models.mock_router import return_model_json_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_novel.actions.enrich import (
    EnrichedNovelComposeRAG,
    StoreEnrichedTexts,
    _qa_pairs_to_chunks,
)
from fabricatio_novel.capabilities.enrich import EnrichChunkTextNovel
from fabricatio_rag.models.qa import EnrichmentResult, QAPair

# ─── Test role ──────────────────────────────────────────────────────────────────


class _EnrichNovelTestRole(ProposeTestRole, EnrichChunkTextNovel):
    """Concrete role combining `ProposeTestRole` and `EnrichChunkTextNovel`."""


@pytest.fixture
def role() -> _EnrichNovelTestRole:
    """Fresh `_EnrichNovelTestRole` per test."""
    return _EnrichNovelTestRole()


# ─── 1. Inheritance smoke tests ──────────────────────────────────────────────────


class TestEnrichInheritance:
    """`EnrichChunkTextNovel` and `StoreEnrichedTexts` shape and MRO."""

    def test_capability_inherits_enrich_verb(self) -> None:
        """`EnrichChunkTextNovel` inherits `enrich()` from `EnrichChunkText`."""
        assert hasattr(EnrichChunkTextNovel, "enrich")
        assert "enrich" in EnrichChunkTextNovel.__dict__ or any(
            "enrich" in cls.__dict__ for cls in EnrichChunkTextNovel.__mro__
        )

    def test_capability_inherits_use_llm(self) -> None:
        """`EnrichChunkTextNovel` is LLM-driven, so it must inherit `UseLLM`."""
        from fabricatio_core.capabilities.usages import UseLLM

        assert issubclass(EnrichChunkTextNovel, UseLLM)

    def test_action_has_ctx_override_true(self) -> None:
        """`StoreEnrichedTexts` follows project convention `ctx_override=True`."""
        assert StoreEnrichedTexts.ctx_override is True

    def test_action_exposes_output_key(self) -> None:
        """`output_key` defaults to `"stored_count"` (mirrors `StoreWritingStyleTexts`).

        Pydantic v2's metaclass blocks class-level attribute access on declared
        fields, so we read the default from `__pydantic_fields__` directly.
        """
        assert StoreEnrichedTexts.model_fields["output_key"].default == "stored_count"

    def test_action_inherits_capability_and_action(self) -> None:
        """`StoreEnrichedTexts` inherits the enrichment capability and `Action`."""
        from fabricatio_core.models.action import Action

        assert issubclass(StoreEnrichedTexts, EnrichedNovelComposeRAG)
        assert issubclass(StoreEnrichedTexts, Action)


# ─── 2. `enrich` capability exercises the LLM end-to-end ───────────────────────


class TestEnrichEndToEnd:
    """`enrich` flows through `Propose.propose` → real validation, returning QAPairs."""

    async def test_single_chunk_returns_enrichment_result(self, role: _EnrichNovelTestRole) -> None:
        """Single-string input returns an `EnrichmentResult` with the mocked `qa_pairs`."""
        result_model = EnrichmentResult(
            qa_pairs=[
                QAPair(question="What is X?", answer="X is ..."),
                QAPair(question="Why Y?", answer="Because ..."),
            ]
        )
        chunk = "unique_chunk_for_test_single_chunk_returns_enrichment_result"

        with install_router_usage(*return_model_json_router_usage(result_model)):
            result = await role.enrich("factual recall", chunk)

        assert isinstance(result, EnrichmentResult)
        assert len(result.qa_pairs) == 2
        assert result.qa_pairs[0].question == "What is X?"

    async def test_batch_chunks_returns_list_in_order(self, role: _EnrichNovelTestRole) -> None:
        """List input returns one `EnrichmentResult` per chunk, preserving order."""
        result_model = EnrichmentResult(
            qa_pairs=[QAPair(question="Q?", answer="A.")],
        )
        chunks = [
            "unique_batch_chunk_0_for_test_batch_chunks_returns_list_in_order",
            "unique_batch_chunk_1_for_test_batch_chunks_returns_list_in_order",
            "unique_batch_chunk_2_for_test_batch_chunks_returns_list_in_order",
        ]

        with install_router_usage(*return_model_json_router_usage(result_model)):
            results = await role.enrich("conceptual", chunks)

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(r, EnrichmentResult) for r in results)
        assert all(len(r.qa_pairs) == 1 for r in results)


# ─── 3. `_qa_pairs_to_chunks` helper ────────────────────────────────────────────


class TestQaPairsToChunks:
    r"""Pure helper: flatten `qa_pairs` to `Question: …\\nAnswer: …` strings."""

    def test_single_pair_flattens(self) -> None:
        """A single `QAPair` produces exactly one chunk in the documented format."""
        pairs = [QAPair(question="Q?", answer="A.")]
        chunks = _qa_pairs_to_chunks(pairs)
        assert chunks == ["Question: Q?\nAnswer: A."]

    def test_multiple_pairs_preserve_order(self) -> None:
        """Order of input pairs is preserved in the output chunks."""
        pairs = [
            QAPair(question="Q1?", answer="A1."),
            QAPair(question="Q2?", answer="A2."),
        ]
        chunks = _qa_pairs_to_chunks(pairs)
        assert chunks == ["Question: Q1?\nAnswer: A1.", "Question: Q2?\nAnswer: A2."]

    def test_empty_input_returns_empty_list(self) -> None:
        """No pairs → empty list (not `[None]` or similar)."""
        assert _qa_pairs_to_chunks([]) == []


# ─── 4. `StoreEnrichedTexts._execute` dispatch and edge cases ───────────────────


def _make_action_with_mocked_storage(monkeypatch: pytest.MonkeyPatch) -> StoreEnrichedTexts:
    """Build a `StoreEnrichedTexts` instance and mock storage + chunking calls on it.

    `_execute` runs three phases: `precise_chunk` (LLM chunking) → `enrich`
    (LLM QA generation) → `add_document` + `rebuild_index` (storage). The
    `TestStoreEnrichedTextsExecute` and `TestStoreEnrichedTextsEnrichPatched`
    groups only intend to exercise the second and third phases — they each
    install exactly one `EnrichmentResult` mock and the chunking phase would
    otherwise consume it (or fail noisily on a non-int response). Mocking
    `precise_chunk` to a one-chunk-per-file passthrough keeps those tests
    focused on the enrich → storage contract.

    Routing notes:
      * `llm_send_to = DUMMY_LLM_GROUP` so the dummy router feeds the action;
        a bare `Action()` otherwise falls back to `CONFIG.llm.send_to`
        (a real provider group) and bypasses the mock.
      * `llm_no_cache = True` so prior runs' cached responses don't leak in
        (mirrors `LLMTestRole`'s default behaviour).

    Pydantic v2 disallows assigning arbitrary instance attributes (e.g.
    `action.add_document = AsyncMock(...)` raises `"object has no field"`),
    so we use `object.__setattr__` to install the mocks directly in the
    instance's `__dict__`. This shadows the inherited class methods for
    the lifetime of the test instance.
    """
    from fabricatio_mock import DUMMY_LLM_GROUP

    action = StoreEnrichedTexts()
    action.llm_send_to = DUMMY_LLM_GROUP
    action.llm_no_cache = True

    async def _fake_precise_chunk(guideline: str, texts, **_kwargs):  # noqa: ANN001, ANN202
        """One chunk per input text — passes each file through untouched."""
        return [[t] for t in texts]

    object.__setattr__(action, "precise_chunk", _fake_precise_chunk)
    object.__setattr__(action, "add_document", AsyncMock(return_value=None))
    object.__setattr__(action, "rebuild_index", AsyncMock(return_value=None))
    return action


class TestStoreEnrichedTextsExecute:
    """`StoreEnrichedTexts._execute` reads files, enriches, stores, and returns count."""

    async def test_empty_file_list_returns_zero(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No files → 0 stored, storage methods not called."""
        action = _make_action_with_mocked_storage(monkeypatch)
        action.text_files = []

        result = await action._execute()

        assert result == 0
        action.add_document.assert_not_called()  # type: ignore[attr-defined]
        action.rebuild_index.assert_not_called()  # type: ignore[attr-defined]

    async def test_single_file_single_pair_dispatches_to_add_document(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """One file, one QAPair: `add_document` is called with one `EnrichedDocument`."""
        target = tmp_path / "src.txt"
        target.write_text("source text for the LLM to enrich", encoding="utf-8")

        result_model = EnrichmentResult(
            qa_pairs=[QAPair(question="Q?", answer="A.")],
        )
        action = _make_action_with_mocked_storage(monkeypatch)
        action.enrich_guideline = "factual"
        action.text_files = [target]
        action.store_config = None

        with install_router_usage(*return_model_json_router_usage(result_model)):
            stored = await action._execute()

        assert stored == 1
        action.add_document.assert_awaited_once()  # type: ignore[attr-defined]
        action.rebuild_index.assert_awaited_once()  # type: ignore[attr-defined]
        # First positional arg is the list of models; one model = one pair.
        models_arg = action.add_document.await_args.args[0]  # type: ignore[attr-defined]
        assert len(models_arg) == 1

    async def test_multiple_files_multiple_pairs_accumulate(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Two files x two QAPairs each -> four models dispatched to `add_document`."""
        files = [tmp_path / f"src{i}.txt" for i in range(2)]
        for f in files:
            f.write_text(f"contents of {f.name}", encoding="utf-8")

        result_model = EnrichmentResult(
            qa_pairs=[
                QAPair(question="Q1?", answer="A1."),
                QAPair(question="Q2?", answer="A2."),
            ]
        )
        action = _make_action_with_mocked_storage(monkeypatch)
        action.enrich_guideline = "conceptual"
        action.text_files = files

        with install_router_usage(*return_model_json_router_usage(result_model)):
            stored = await action._execute()

        # 2 files x 2 pairs = 4 chunks.
        assert stored == 4
        models_arg = action.add_document.await_args.args[0]  # type: ignore[attr-defined]
        assert len(models_arg) == 4
        # All dispatched models must be EnrichedDocument instances with the
        # flattened "Question: … / Answer: …" payload.
        from fabricatio_novel.models.novel_enrich import EnrichedDocument

        assert all(isinstance(m, EnrichedDocument) for m in models_arg)
        assert all(m.content.startswith("Question: ") for m in models_arg)

    async def test_empty_qa_pairs_returns_zero_without_calling_storage(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Enrichment returning zero pairs → guard short-circuits storage calls."""
        target = tmp_path / "src.txt"
        target.write_text("source text", encoding="utf-8")

        empty_model = EnrichmentResult(qa_pairs=[])
        action = _make_action_with_mocked_storage(monkeypatch)
        action.enrich_guideline = "anything"
        action.text_files = [target]

        with install_router_usage(*return_model_json_router_usage(empty_model)):
            stored = await action._execute()

        assert stored == 0
        action.add_document.assert_not_called()  # type: ignore[attr-defined]
        action.rebuild_index.assert_not_called()  # type: ignore[attr-defined]


# ─── 5. Patching the underlying `enrich` to bypass LLM entirely ────────────────


class TestStoreEnrichedTextsEnrichPatched:
    """Mock `enrich()` directly to verify the action's batch + count contract."""

    async def test_enrich_called_with_all_file_texts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """`enrich()` receives every file's text content in order."""
        files = [tmp_path / f"src{i}.txt" for i in range(3)]
        for i, f in enumerate(files):
            f.write_text(f"content_{i}", encoding="utf-8")

        action = _make_action_with_mocked_storage(monkeypatch)
        action.enrich_guideline = "the-guideline"
        action.text_files = files

        # Mock enrich to return one empty EnrichmentResult per file (so
        # the storage guard short-circuits and we never exercise add_document).
        async def _fake_enrich(_self, guideline: str, texts: List[str]) -> List[EnrichmentResult]:  # noqa: ANN001
            assert guideline == "the-guideline"
            assert texts == ["content_0", "content_1", "content_2"]
            return [EnrichmentResult(qa_pairs=[])] * len(texts)

        with patch.object(EnrichChunkTextNovel, "enrich", autospec=True, side_effect=_fake_enrich):
            stored = await action._execute()

        assert stored == 0
