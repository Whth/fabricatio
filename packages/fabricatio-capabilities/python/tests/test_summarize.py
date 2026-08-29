"""Tests for the Summarize capability."""

from typing import TYPE_CHECKING

import pytest
from fabricatio_capabilities.capabilities.summarize import (
    LengthType,
    Summarize,
    _length,
    _render_summarize_prompt,
    _resolve_min_length,
)
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_router_usage
from fabricatio_mock.utils import install_router_usage

if TYPE_CHECKING:
    import pytest_mock


class SummarizeTestRole(LLMTestRole, Summarize):
    """Test role mixing the dummy LLM into the Summarize capability."""


@pytest.fixture
def role() -> SummarizeTestRole:
    """Instantiate the test role for each test."""
    return SummarizeTestRole(name="summarize")


@pytest.mark.parametrize(
    ("text", "length_type", "expected"),
    [
        ("hello", LengthType.Chars, 5),
        ("héllo wörld", LengthType.Chars, 11),
        ("one two three", LengthType.Words, 3),
        ("  spaced   out  ", LengthType.Words, 2),
        ("First. Second!", LengthType.Sentences, 2),
        ("你好。世界！", LengthType.Sentences, 2),
        ("No punctuation here", LengthType.Sentences, 1),
        ("¿Qué?", LengthType.Sentences, 1),
        ("", LengthType.Sentences, 0),
    ],
)
def test_length_counts(text: str, length_type: LengthType, expected: int) -> None:
    """The length counter matches the documented unit semantics."""
    assert _length(text, length_type) == expected


def test_resolve_min_length() -> None:
    """The default floor is 80% of the ceiling (at least 1); explicit bounds are validated."""
    assert _resolve_min_length(None, 10) == 8
    assert _resolve_min_length(None, 1) == 1
    assert _resolve_min_length(None, 4) == 3
    assert _resolve_min_length(5, 10) == 5
    with pytest.raises(ValueError, match="min_length"):
        _resolve_min_length(11, 10)
    with pytest.raises(ValueError, match="min_length"):
        _resolve_min_length(0, 10)


@pytest.mark.asyncio
async def test_summarize_returns_text_within_window(role: SummarizeTestRole) -> None:
    """A response inside the length window is returned."""
    with install_router_usage("short text"):
        result = await role.summarize(
            "A much longer piece of raw text that needs shortening.",
            max_length=10,
            requirement="keep the main idea",
        )
    assert result == "short text"


@pytest.mark.asyncio
async def test_summarize_strips_surrounding_whitespace(role: SummarizeTestRole) -> None:
    """Leading and trailing whitespace is trimmed before measuring and returning."""
    with install_router_usage("  short  "):
        result = await role.summarize(
            "A much longer piece of raw text that needs shortening.",
            max_length=10,
            min_length=1,
        )
    assert result == "short"


@pytest.mark.asyncio
async def test_summarize_rejects_oversized_response(role: SummarizeTestRole) -> None:
    """Responses over the ceiling fail validation on every attempt and surface as None."""
    with install_router_usage(*return_router_usage("this is far too long", "still far too long", "way over the bound")):
        result = await role.summarize(
            "A much longer piece of raw text that needs shortening.",
            max_length=10,
            min_length=1,
        )
    assert result is None


@pytest.mark.asyncio
async def test_summarize_rejects_under_min_length(role: SummarizeTestRole) -> None:
    """A response below the explicit floor fails validation and surfaces as None."""
    with install_router_usage(*return_router_usage("tiny", "tiny", "tiny")):
        result = await role.summarize(
            "A much longer piece of raw text that needs shortening.",
            max_length=100,
            min_length=50,
        )
    assert result is None


@pytest.mark.asyncio
async def test_summarize_derived_min_enforced(role: SummarizeTestRole) -> None:
    """The default floor (80% of the ceiling) rejects an overly short response."""
    with install_router_usage(*return_router_usage("tiny", "tiny", "tiny")):
        result = await role.summarize(
            "A much longer piece of raw text that needs shortening.",
            max_length=100,
        )
    assert result is None


@pytest.mark.asyncio
async def test_summarize_retries_until_within_window(role: SummarizeTestRole) -> None:
    """An out-of-window first response is retried and the valid one is returned."""
    with install_router_usage("way too long for the bound", "ok text"):
        result = await role.summarize(
            "A much longer piece of raw text that needs shortening.",
            max_length=10,
            min_length=1,
        )
    assert result == "ok text"


@pytest.mark.asyncio
async def test_summarize_measures_words(role: SummarizeTestRole) -> None:
    """The Words unit counts whitespace-separated tokens against the window."""
    with install_router_usage("one two three"):
        result = await role.summarize(
            "A much longer piece of raw text that needs shortening.",
            max_length=3,
            length_type=LengthType.Words,
        )
    assert result == "one two three"


@pytest.mark.asyncio
async def test_summarize_measures_sentences(role: SummarizeTestRole) -> None:
    """The Sentences unit counts sentence-ending punctuation against the window."""
    with install_router_usage("First sentence. Second sentence!"):
        result = await role.summarize(
            "A much longer piece of raw text that needs shortening.",
            max_length=2,
            length_type=LengthType.Sentences,
        )
    assert result == "First sentence. Second sentence!"


@pytest.mark.asyncio
async def test_summarize_embeds_raw_text_in_prompt(
    role: SummarizeTestRole, mocker: "pytest_mock.MockerFixture"
) -> None:
    """The raw text, requirement, and length bounds reach the rendered prompt."""
    spy = mocker.patch.object(Summarize, "aask", autospec=True)
    spy.return_value = "ok"

    result = await role.summarize(
        "RAW TEXT TO SUMMARIZE",
        max_length=10,
        requirement="keep the main idea",
        min_length=1,
        length_type=LengthType.Words,
    )

    assert result == "ok"
    question = spy.call_args.kwargs["question"]
    assert "RAW TEXT TO SUMMARIZE" in question
    assert "keep the main idea" in question
    assert "10 words" in question


@pytest.mark.asyncio
async def test_force_summarize_returns_when_window_met_first_pass(role: SummarizeTestRole) -> None:
    """A within-window first response is returned after a single pass."""
    with install_router_usage("ok text"):
        result = await role.force_summarize("RAW SOURCE", max_length=10, min_length=1)
    assert result == "ok text"


@pytest.mark.asyncio
async def test_force_summarize_feeds_back_overlong_attempt(
    role: SummarizeTestRole, mocker: "pytest_mock.MockerFixture"
) -> None:
    """An oversized output is fed back as the input of the next pass."""
    spy = mocker.patch.object(Summarize, "aask", autospec=True)
    spy.side_effect = ["way too long content here", "ok text"]

    result = await role.force_summarize("RAW SOURCE", max_length=10, min_length=1)

    assert result == "ok text"
    questions = [call.kwargs["question"] for call in spy.call_args_list]
    assert len(questions) == 2
    assert "RAW SOURCE" in questions[0]
    assert "way too long content here" in questions[1]


@pytest.mark.asyncio
async def test_force_summarize_restarts_from_raw_when_under_min(
    role: SummarizeTestRole, mocker: "pytest_mock.MockerFixture"
) -> None:
    """An under-min output restarts the next pass from the original raw text."""
    spy = mocker.patch.object(Summarize, "aask", autospec=True)
    spy.side_effect = ["tiny", "ok text"]

    result = await role.force_summarize("RAW SOURCE", max_length=10, min_length=6)

    assert result == "ok text"
    questions = [call.kwargs["question"] for call in spy.call_args_list]
    assert "RAW SOURCE" in questions[1]


@pytest.mark.asyncio
async def test_force_summarize_returns_closest_when_window_unreachable(role: SummarizeTestRole) -> None:
    """The attempt closest to the window is returned when the window stays unreachable."""
    with install_router_usage("twenty chars long text!", "still too long!!", "over bound!"):
        result = await role.force_summarize(
            "RAW SOURCE",
            max_length=5,
            min_length=1,
            max_iterations=3,
        )
    assert result == "over bound!"
    assert len(result) > 5


@pytest.mark.asyncio
async def test_force_summarize_returns_none_when_all_passes_fail(role: SummarizeTestRole) -> None:
    """Every empty pass surfaces as None."""
    with install_router_usage("", "", ""):
        result = await role.force_summarize(
            "RAW SOURCE",
            max_length=10,
            min_length=1,
            max_iterations=3,
        )
    assert result is None


@pytest.mark.asyncio
async def test_render_prompt_contains_bounds_and_text() -> None:
    """The rendered prompt carries the window bounds, raw text, and conditional requirement."""
    p = _render_summarize_prompt("hello world", "keep tone", 5, 10, LengthType.Words)
    assert "Minimum: 5" in p
    assert "Maximum: 10" in p
    assert "hello world" in p
    assert "Summarization Requirement" in p
    assert "{{" not in p

    q = _render_summarize_prompt("hello world", "", 5, 10, LengthType.Words)
    assert "Summarization Requirement" not in q
