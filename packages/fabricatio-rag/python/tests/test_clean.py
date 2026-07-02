"""Integration tests for `fabricatio_rag.capabilities.clean.CleanText`.

`CleanText.clean` delegates to `HashlineEdit.hashline_diff`, which runs a
self-correcting LLM loop. These tests exercise the loop end-to-end via the
`fabricatio_mock` router, mirroring the pattern in
`fabricatio-diff/tests/test_hashline_edit.py`.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fabricatio_diff.capabilities.hashline_edit import HashlineDiffResult, HashlineEdit, HashlineEditExhaustedError
from fabricatio_diff.config import diff_config
from fabricatio_diff.rust import format_hashes
from fabricatio_diff.utils import HashlineDelimiters
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_router_usage
from fabricatio_mock.utils import install_router_usage
from fabricatio_rag.capabilities.clean import CleanText


def _make_diff_result(content: str) -> HashlineDiffResult:
    """Build a minimal satisfied HashlineDiffResult for mock returns."""
    return HashlineDiffResult(content=content, applied_edits=[], iterations=1, satisfied=True)


# ─── Stub templates ────────────────────────────────────────────────────
# Reuse the hashline_diff / hashline_judge templates indirectly via the
# `diff_config` overrides; we install local stubs so we don't depend on the
# (not-yet-shipped) built-in templates at the workspace level.

_STUB_HASHLINE_DIFF_TEMPLATE = """\
SOURCE:
{{source}}
REQUIREMENT: {{requirement}}
LAST_ERROR: {{last_error}}
"""

_STUB_HASHLINE_JUDGE_TEMPLATE = """\
REQUIREMENT: {{requirement}}
CONTENT:
{{content}}
"""


@pytest.fixture
def stub_hashline_templates(tmp_path: Path) -> tuple[str, str]:
    """Install stub .hbs templates under `test/*` and return their names."""
    test_dir = tmp_path / "templates"
    test_dir.mkdir()
    (test_dir / "test_hashline_diff.hbs").write_text(_STUB_HASHLINE_DIFF_TEMPLATE)
    (test_dir / "test_hashline_judge.hbs").write_text(_STUB_HASHLINE_JUDGE_TEMPLATE)

    from fabricatio_core import TEMPLATE_MANAGER

    TEMPLATE_MANAGER.add_store(test_dir, rediscovery=True)
    return "test/test_hashline_diff", "test/test_hashline_judge"


@pytest.fixture
def with_stub_templates(
    stub_hashline_templates: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str]:
    """Patch `diff_config` to reference the stub templates and clamp iteration count."""
    diff_name, judge_name = stub_hashline_templates
    monkeypatch.setattr(diff_config, "hashline_diff_template", diff_name)
    monkeypatch.setattr(diff_config, "hashline_judge_template", judge_name)
    monkeypatch.setattr(diff_config, "hashline_diff_max_iterations", 3)
    return diff_name, judge_name


# ─── Test role ─────────────────────────────────────────────────────────


class CleanTextTestRole(LLMTestRole, CleanText):
    """Concrete test role combining LLMTestRole with CleanText."""


@pytest.fixture
def role() -> CleanTextTestRole:
    """A fresh CleanTextTestRole per test."""
    return CleanTextTestRole()


# ─── 1. HashlineEdit inheritance smoke test ────────────────────────────


class TestCleanTextInheritance:
    """`CleanText` must inherit `HashlineEdit` to expose `clean`."""

    def test_is_hashline_edit_subclass(self) -> None:
        """Static class check: CleanText is a HashlineEdit subclass."""
        assert issubclass(CleanText, HashlineEdit)

    def test_role_is_both(self, role: CleanTextTestRole) -> None:
        """Instance check + inherited surface verification."""
        assert isinstance(role, CleanText)
        assert isinstance(role, HashlineEdit)
        # Inherited from HashlineEdit → UseLLM
        assert hasattr(role, "hashline_diff")
        assert hasattr(role, "compute_line_hash")
        assert hasattr(role, "format_hashes")


# ─── 2. `clean` delegates to `hashline_diff` ───────────────────────────


class TestCleanDelegatesToHashlineDiff:
    """`clean(text, guideline)` must wrap `hashline_diff` per input text."""

    @pytest.mark.asyncio
    async def test_single_text_satisfied_first_try(
        self,
        role: CleanTextTestRole,
        with_stub_templates: tuple[str, str],
    ) -> None:
        """LLM emits a valid edit + judge YES → cleaned string returned."""
        source = "alpha\nbeta\ngamma"
        anchor_2 = format_hashes(source).split("\n")[1].split("|")[0]
        llm_response = (
            f"{HashlineDelimiters.SET_LEFT.value} {anchor_2}\nBETA_CLEAN\n{HashlineDelimiters.SET_RIGHT.value}"
        )
        # 1 edit emission + 1 judge YES = 2 router calls
        with install_router_usage(*return_router_usage(llm_response, "YES")):
            result = await role.clean("rename line2 to BETA_CLEAN", source)

        assert isinstance(result, str)
        assert result == "alpha\nBETA_CLEAN\ngamma"

    @pytest.mark.asyncio
    async def test_returns_str_for_str_input(
        self,
        role: CleanTextTestRole,
        with_stub_templates: tuple[str, str],
    ) -> None:
        """Single string input must return a string (not a list)."""
        source = "x\ny"
        anchor = format_hashes(source).split("\n")[1].split("|")[0]
        resp = f"{HashlineDelimiters.SET_LEFT.value} {anchor}\nY\n{HashlineDelimiters.SET_RIGHT.value}"
        with install_router_usage(*return_router_usage(resp, "YES")):
            result = await role.clean("rename line2", source)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_exhausts_and_raises(
        self,
        role: CleanTextTestRole,
        with_stub_templates: tuple[str, str],
    ) -> None:
        """If `hashline_diff` can't satisfy, `clean` propagates the error."""
        source = "x\ny"
        anchor = format_hashes(source).split("\n")[1].split("|")[0]
        resp = f"{HashlineDelimiters.SET_LEFT.value} {anchor}\nY\n{HashlineDelimiters.SET_RIGHT.value}"
        # max_iterations=3 → 3 emit + 3 judge NO = 6 calls
        with (
            install_router_usage(*return_router_usage(resp, "NO", resp, "NO", resp, "NO")),
            pytest.raises(HashlineEditExhaustedError),
        ):
            await role.clean("any requirement", source)


# ─── 3. Batch dispatch (was_str + gather) via AsyncMock ────────────────
# `install_router_usage` is not safe for concurrent consumption (shared LIFO
# pop), so we mock `hashline_diff` directly to verify `clean`'s batch
# contract: parallel dispatch + correct was_str unwrapping.


class TestCleanBatchDispatch:
    """Verify `clean` calls `hashline_diff` per text in parallel and unwraps `.content`.

    `install_router_usage` is not safe for concurrent consumption (shared LIFO
    pop), so we mock `hashline_diff` directly to verify `clean`'s batch
    contract: parallel dispatch + correct was_str unwrapping.
    """

    @pytest.mark.asyncio
    async def test_list_input_returns_list_of_strings(self, role: CleanTextTestRole) -> None:
        """List input → list of strings, parallel length, content extracted."""

        async def fake(self: HashlineEdit, source: str, requirement: str) -> HashlineDiffResult:
            return _make_diff_result(f"CLEANED::{source}")

        with patch.object(HashlineEdit, "hashline_diff", autospec=True, side_effect=fake):
            result = await role.clean("anything", ["a", "b", "c"])

        assert isinstance(result, list)
        assert result == ["CLEANED::a", "CLEANED::b", "CLEANED::c"]

    @pytest.mark.asyncio
    async def test_str_input_returns_single_string(self, role: CleanTextTestRole) -> None:
        """Single string input → unwrapped string, not a 1-element list."""

        async def fake(self: HashlineEdit, source: str, requirement: str) -> HashlineDiffResult:
            return _make_diff_result(f"CLEANED::{source}")

        with patch.object(HashlineEdit, "hashline_diff", autospec=True, side_effect=fake):
            result = await role.clean("anything", "only_one")

        assert isinstance(result, str)
        assert result == "CLEANED::only_one"

    @pytest.mark.asyncio
    async def test_batch_invokes_hashline_diff_per_text(self, role: CleanTextTestRole) -> None:
        """Each input text must trigger exactly one `hashline_diff` call."""
        call_log: list[str] = []

        async def fake(self: HashlineEdit, source: str, requirement: str) -> HashlineDiffResult:
            call_log.append(source)
            return _make_diff_result(source)

        with patch.object(HashlineEdit, "hashline_diff", autospec=True, side_effect=fake):
            await role.clean("the guideline", ["x", "y", "z", "w"])

        assert sorted(call_log) == ["w", "x", "y", "z"]
        assert len(call_log) == 4

    @pytest.mark.asyncio
    async def test_batch_propagates_exhausted_error(self, role: CleanTextTestRole) -> None:
        """If any text exhausts, the underlying error surfaces through `gather`."""

        async def fake(self: HashlineEdit, source: str, requirement: str) -> HashlineDiffResult:
            if source == "bad":
                raise HashlineEditExhaustedError(
                    "exhausted",
                    iterations=3,
                    last_source="bad",
                    last_error="judge NO",
                )
            return _make_diff_result(source)

        with (
            patch.object(HashlineEdit, "hashline_diff", autospec=True, side_effect=fake),
            pytest.raises(HashlineEditExhaustedError),
        ):
            await role.clean("g", ["good", "bad", "good2"])


# ─── 4. End-to-end with realistic input ────────────────────────────────


class TestCleanTextEndToEnd:
    """A more realistic clean scenario: strip markup-ish patterns via hashline edits."""

    @pytest.mark.asyncio
    async def test_clean_replaces_line_with_empty(
        self,
        role: CleanTextTestRole,
        with_stub_templates: tuple[str, str],
    ) -> None:
        """LLM replaces a noisy line with an empty string — surrounding content preserved."""
        source = "header\n<b>noisy</b>\nfooter"
        anchor = format_hashes(source).split("\n")[1].split("|")[0]
        resp = f"{HashlineDelimiters.SET_LEFT.value} {anchor}\n{HashlineDelimiters.SET_RIGHT.value}"
        with install_router_usage(*return_router_usage(resp, "YES")):
            result = await role.clean("remove all markup", source)

        assert isinstance(result, str)
        assert "<b>" not in result
        assert result.startswith("header\n")
        assert result.endswith("footer")
