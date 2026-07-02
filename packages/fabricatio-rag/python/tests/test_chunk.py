"""Integration tests for `fabricatio_rag.capabilities.chunk.PreciseChunkText`.

`PreciseChunkText.precise_chunk` splits text into mini-chunks, asks the LLM
for split-point indices via `alist_v(rendered, int)`, then merges the mini
chunks by those indices. These tests cover the merge logic and dispatch
contract end-to-end via the `fabricatio_mock` router.
"""

import inspect
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_json_router_usage, return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_rag.capabilities.chunk import PreciseChunkText
from fabricatio_rag.config import rag_config

# ─── Stub template ─────────────────────────────────────────────────────
# Real `built-in/precise_chunk` is not shipped at the workspace level, so we
# install a local stub and override the rag config to point at it.

_STUB_PRECISE_CHUNK_TEMPLATE = """\
GUIDELINE: {{guideline}}
MIN: {{min_size}}  MAX: {{max_size}}
SEGMENTS:
{{#each mini_chunks}}
[{{@index}}] {{{this}}}
{{/each}}
"""


@pytest.fixture
def stub_precise_chunk_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Install a stub `precise_chunk` template and override the rag config."""
    test_dir = tmp_path / "templates"
    test_dir.mkdir()
    (test_dir / "test_precise_chunk.hbs").write_text(_STUB_PRECISE_CHUNK_TEMPLATE)

    from fabricatio_core import TEMPLATE_MANAGER

    TEMPLATE_MANAGER.add_store(test_dir, rediscovery=True)

    name = "test/test_precise_chunk"
    monkeypatch.setattr(rag_config, "precise_chunk_template", name)
    return name


# ─── Test role ─────────────────────────────────────────────────────────


class PreciseChunkTestRole(LLMTestRole, PreciseChunkText):
    """Concrete test role combining LLMTestRole with PreciseChunkText."""


@pytest.fixture
def role() -> PreciseChunkTestRole:
    """A fresh PreciseChunkTestRole per test."""
    return PreciseChunkTestRole()


# ─── 1. Dispatch contract ──────────────────────────────────────────────


class TestPreciseChunkDispatch:
    """Verify overload signatures and input→output dispatch."""

    def test_concrete_impl_accepts_union(self) -> None:
        """Concrete impl signature accepts `str | List[str]`."""
        sig = inspect.signature(PreciseChunkText.precise_chunk)
        text_param = sig.parameters["text"]
        assert text_param.annotation == "str | List[str]"

    @pytest.mark.asyncio
    async def test_str_input_returns_list_of_strings(
        self,
        role: PreciseChunkTestRole,
        stub_precise_chunk_template: str,
    ) -> None:
        """Single string input → `List[str]` (one chunk per element)."""
        text = "abcdefghij" * 20  # 200 chars at mini_chunk_size=128 → 2 mini-chunks

        # Mock alist_v directly so we don't depend on JSON parsing
        async def fixed_splits(self: Any, requirement: Any, value_type: Any, **kw: Any) -> list[int]:
            return [0, 1]

        with patch.object(UseLLM, "alist_v", autospec=True, side_effect=fixed_splits):
            result = await role.precise_chunk("any guideline", text, mini_chunk_size=128)

        assert isinstance(result, list)
        assert all(isinstance(c, str) for c in result)
        assert len(result) >= 1
        # Concatenation recovers the original text
        assert "".join(result) == text

    @pytest.mark.asyncio
    async def test_list_input_returns_list_of_lists(
        self,
        role: PreciseChunkTestRole,
        stub_precise_chunk_template: str,
    ) -> None:
        """List input → `List[List[str]]` (one chunk-list per input)."""
        texts = ["alpha " * 30, "beta " * 30]  # each ~150 chars at mini_chunk_size=128 → 2 mini each

        async def fixed_splits(self: Any, requirement: Any, value_type: Any, **kw: Any) -> list[list[int]]:
            # When input is a list, alist_v returns List[List[int] | None].
            # All splits are non-None and say "one chunk each".
            return [[0, 1], [0, 1]]

        with patch.object(UseLLM, "alist_v", autospec=True, side_effect=fixed_splits):
            result = await role.precise_chunk("guideline", texts, mini_chunk_size=128)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(r, list) for r in result)
        assert all(isinstance(s, str) for r in result for s in r)
        # Reconstructed text per input
        assert "".join(result[0]) == texts[0]
        assert "".join(result[1]) == texts[1]


# ─── 2. Merge logic for known splits ───────────────────────────────────


class TestPreciseChunkMerge:
    """Verify the mini-chunk merge logic with known split indices."""

    @pytest.mark.asyncio
    async def test_splits_cover_all_mini_chunks(
        self,
        role: PreciseChunkTestRole,
        stub_precise_chunk_template: str,
    ) -> None:
        """Splits like [0, 5, 10] on N mini-chunks produce chunks covering all of them."""
        text = "abcdefghij" * 200  # 2000 chars → 16 mini-chunks at size 128

        async def fixed_splits(self: Any, requirement: Any, value_type: Any, **kw: Any) -> list[int]:
            return [0, 5, 10]

        with patch.object(UseLLM, "alist_v", autospec=True, side_effect=fixed_splits):
            result = await role.precise_chunk(
                "g",
                text,
                mini_chunk_size=128,
            )

        assert isinstance(result, list)
        assert all(isinstance(c, str) for c in result)
        assert len(result) >= 1
        assert "".join(result) == text

    @pytest.mark.asyncio
    async def test_alist_v_none_falls_back_to_single_chunk(
        self,
        role: PreciseChunkTestRole,
        stub_precise_chunk_template: str,
    ) -> None:
        """If `alist_v` returns None, the entire input becomes one chunk."""
        text = "hello world"

        async def none_splits(self: Any, requirement: Any, value_type: Any, **kw: Any) -> None:
            return None

        with patch.object(UseLLM, "alist_v", autospec=True, side_effect=none_splits):
            result = await role.precise_chunk("g", text, mini_chunk_size=4)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == text

    @pytest.mark.asyncio
    async def test_out_of_bounds_splits_are_skipped(
        self,
        role: PreciseChunkTestRole,
        stub_precise_chunk_template: str,
    ) -> None:
        """Split indices ≥ len(mini_chunks) are silently skipped."""
        text = "abcdefghij" * 50  # 500 chars → 4 mini at size 128

        async def oob_splits(self: Any, requirement: Any, value_type: Any, **kw: Any) -> list[int]:
            # 0 is valid; 9999 is out-of-bounds
            return [0, 9999]

        with patch.object(UseLLM, "alist_v", autospec=True, side_effect=oob_splits):
            result = await role.precise_chunk("g", text, mini_chunk_size=128)

        assert isinstance(result, list)
        assert "".join(result) == text


# ─── 3. End-to-end with real router JSON response ──────────────────────


class TestPreciseChunkEndToEnd:
    """Full end-to-end with the JSON-formatted router response."""

    @pytest.mark.asyncio
    async def test_round_trip_with_json_response(
        self,
        role: PreciseChunkTestRole,
        stub_precise_chunk_template: str,
    ) -> None:
        """A real JSON-array response from the router is parsed and applied."""
        text = "lorem ipsum dolor sit amet " * 50  # ~1350 chars
        # Whatever splits the LLM returns, the join must recover the input.
        with install_router_usage(*return_json_router_usage("[0]")):
            result = await role.precise_chunk("any guideline", text, mini_chunk_size=128)

        assert isinstance(result, list)
        assert "".join(result) == text

    @pytest.mark.asyncio
    async def test_unparseable_response_falls_back(
        self,
        role: PreciseChunkTestRole,
        stub_precise_chunk_template: str,
    ) -> None:
        """A non-JSON response from the router → `alist_v` returns None → fallback."""
        text = "hello world"
        # Return plain text that's not a JSON array; the rust validator will
        # reject it and alist_v returns None.
        with install_router_usage(*return_router_usage("not a json array")):
            result = await role.precise_chunk("g", text, mini_chunk_size=10)

        # Fallback path: entire text as one chunk.
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == text
