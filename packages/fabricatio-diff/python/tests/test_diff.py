"""Tests for the diff."""

import pytest
from fabricatio_diff.capabilities.diff_edit import DiffEdit
from fabricatio_diff.models.diff import Diff
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_router_usage
from fabricatio_mock.utils import install_router_usage


def diff_factory(search: str, replace: str) -> Diff:
    """Create Diff object with test data.

    Args:
        search (str): Search string for the diff
        replace (str): Replace string for the diff

    Returns:
        Diff: Diff object with search and replace strings
    """
    return Diff(search=search, replace=replace)


class DiffEditRole(LLMTestRole, DiffEdit):
    """A class that tests the diff edit methods."""


@pytest.fixture
def responses(ret_value: Diff) -> list[str]:
    """Create a responses fixture that returns a specific value.

    Args:
        ret_value (SketchedAble): Value to be returned by the router

    Returns:
        list[str]: Response strings
    """
    return return_router_usage(ret_value.display())


@pytest.fixture
def role() -> DiffEditRole:
    """Create a DiffEditRole instance for testing.

    Returns:
        DiffEditRole: DiffEditRole instance
    """
    return DiffEditRole()


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement", "expected_result"),
    [
        (
            diff_factory("old text", "new text"),
            "This is old text in a file",
            "Replace old text with new text",
            None,
        ),
        (diff_factory("hello", "world"), "hello there", "Change greeting", None),
        (
            diff_factory("def function old_name():", "def function new_name():"),
            "def function old_name():\n    pass",
            "Rename function",
            "def function new_name():\n    pass",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_edit_success(
    responses: list[str], role: DiffEditRole, ret_value: Diff, source: str, requirement: str, expected_result: str
) -> None:
    """Test the diff_edit method with successful cases.

    Args:
        responses (list[str]): Mocked response strings
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text to edit
        requirement (str): Requirement for the edit
        expected_result (str): Expected result after applying diff
    """
    with install_router_usage(*responses):
        result = await role.diff_edit(source, requirement)
        assert result == expected_result


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement"),
    [
        (
            diff_factory("This is old text in a file", "This is new text in a file"),
            "This is old text in a file",
            "q_diff_method_1",
        ),
        (
            diff_factory("hello there", "world there"),
            "hello there",
            "q_diff_method_2",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_method(
    responses: list[str], role: DiffEditRole, ret_value: Diff, source: str, requirement: str
) -> None:
    """Test the diff method returns correct Diff object.

    Args:
        responses (list[str]): Mocked response strings
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text for diff
        requirement (str): Requirement for the diff
    """
    with install_router_usage(*responses):
        diff = await role.diff(source, requirement)
        assert diff is not None
        assert diff.search == ret_value.search
        assert diff.replace == ret_value.replace


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement"),
    [
        (
            diff_factory("nonexistent line", "replacement line"),
            "original text",
            "q_diff_no_match_1",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_edit_no_match(
    responses: list[str], role: DiffEditRole, ret_value: Diff, source: str, requirement: str
) -> None:
    """Test diff_edit when search string doesn't match source.

    Args:
        responses (list[str]): Mocked response strings
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
    """
    with install_router_usage(*responses):
        result = await role.diff_edit(source, requirement)
        # Should return None when no match is found
        assert result is None


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement", "match_precision", "expected"),
    [
        (
            diff_factory("original text here", "original content here"),
            "original text here",
            "q_diff_precision_1",
            0.8,
            "original content here",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_edit_with_precision(
    responses: list[str],
    role: DiffEditRole,
    ret_value: Diff,
    source: str,
    requirement: str,
    match_precision: float,
    expected: str,
) -> None:
    """Test diff_edit with custom match precision.

    Args:
        responses (list[str]): Mocked response strings
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
        match_precision (float): Match precision value
        expected (str): Expected result
    """
    with install_router_usage(*responses):
        result = await role.diff_edit(source, requirement, match_precision=match_precision)
        assert result == expected


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement", "expected"),
    [
        (
            diff_factory("", "new content"),
            "",
            "Add content",
            None,
        ),
        (
            diff_factory("content", ""),
            "content",
            "remove content",
            "",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_edit_empty_source(
    responses: list[str], role: DiffEditRole, ret_value: Diff, source: str, requirement: str, expected: str
) -> None:
    """Test diff_edit with empty source string.

    Args:
        responses (list[str]): Mocked response strings
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
        expected (str): Expected result
    """
    with install_router_usage(*responses):
        result = await role.diff_edit(source, requirement)
        assert result == expected


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement"),
    [
        (
            Diff(search="", replace=""),
            "source text",
            "q_diff_none_resp_1",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_method_returns_none_on_invalid_response(
    responses: list[str], role: DiffEditRole, ret_value: Diff, source: str, requirement: str
) -> None:
    """Test diff method returns None when LLM response is invalid.

    Args:
        responses (list[str]): Mocked response strings
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object (invalid)
        source (str): Source text
        requirement (str): Requirement for diff
    """
    with install_router_usage(*responses):
        diff = await role.diff(source, requirement)
        # The _validator should return None for invalid diffs
        assert diff is None


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement", "expected"),
    [
        (
            diff_factory("hello world", "hi world"),
            "hello world",
            "q_diff_various_1",
            "hi world",
        ),
        (
            diff_factory("hello\nhello", "hi\nhi"),
            "hello\nhello",
            "q_diff_various_2",
            "hi\nhi",
        ),
        (
            diff_factory("exact match", "perfect fit"),
            "exact match",
            "q_diff_various_3",
            "perfect fit",
        ),
        (
            diff_factory("Case sensitive", "case sensitive"),
            "case sensitive",
            "q_diff_various_4",
            None,
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_edit_various_cases(
    responses: list[str], role: DiffEditRole, ret_value: Diff, source: str, requirement: str, expected: str
) -> None:
    """Test diff_edit with various search and replace scenarios.

    Args:
        responses (list[str]): Mocked response strings
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
        expected (str): Expected result
    """
    with install_router_usage(*responses):
        result = await role.diff_edit(source, requirement)
        assert result == expected


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement", "expected"),
    [
        (
            diff_factory("old line", "new line"),
            "line 1\nold line\nline 3",
            "Update middle line",
            "line 1\nnew line\nline 3",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_edit_multiline(
    responses: list[str], role: DiffEditRole, ret_value: Diff, source: str, requirement: str, expected: str
) -> None:
    """Test diff_edit with multiline text.

    Args:
        responses (list[str]): Mocked response strings
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
        expected (str): Expected result
    """
    with install_router_usage(*responses):
        result = await role.diff_edit(source, requirement)
        assert result == expected


class TestDiffHashlineSupport:
    """Test suite for Diff hashline support methods."""

    def test_from_anchors_creation(self) -> None:
        """Test creating a Diff from hashline anchors."""
        diff = Diff.from_anchors(
            start_anchor="1:abc123",
            end_anchor="3:def456",
            replace="replacement content",
        )
        assert diff.start_anchor == "1:abc123"
        assert diff.end_anchor == "3:def456"
        assert diff.replace == "replacement content"
        assert diff.search == ""
        assert diff.start_line is None
        assert diff.end_line is None

    def test_from_line_range_creation(self) -> None:
        """Test creating a Diff from line numbers."""
        diff = Diff.from_line_range(
            start=5,
            end=10,
            replace="new lines here",
        )
        assert diff.start_line == 5
        assert diff.end_line == 10
        assert diff.replace == "new lines here"
        assert diff.search == ""
        assert diff.start_anchor is None
        assert diff.end_anchor is None

    def test_reverse_preserves_anchors(self) -> None:
        """Test that reverse() swaps anchor fields correctly."""
        original = Diff.from_anchors(
            start_anchor="1:abc",
            end_anchor="5:def",
            replace="replacement",
        )
        reversed_diff = original.reverse()

        assert reversed_diff.start_anchor == "5:def"
        assert reversed_diff.end_anchor == "1:abc"
        assert reversed_diff.search == "replacement"
        assert reversed_diff.replace == ""

    def test_reverse_preserves_line_numbers(self) -> None:
        """Test that reverse() swaps line number fields correctly."""
        original = Diff.from_line_range(
            start=10,
            end=20,
            replace="new content",
        )
        reversed_diff = original.reverse()

        assert reversed_diff.start_line == 20
        assert reversed_diff.end_line == 10
        assert reversed_diff.search == "new content"
        assert reversed_diff.replace == ""

    def test_from_anchors_and_reverse_roundtrip(self) -> None:
        """Test that from_anchors + reverse + reverse gives back original anchors."""
        original = Diff.from_anchors(
            start_anchor="2:mno",
            end_anchor="4:pqr",
            replace="text",
        )
        # Double reverse should restore original
        restored = original.reverse().reverse()

        assert restored.start_anchor == original.start_anchor
        assert restored.end_anchor == original.end_anchor
        assert restored.search == original.search
        assert restored.replace == original.replace

    def test_backward_compatibility_search_replace(self) -> None:
        """Test that old search/replace usage still works."""
        diff = Diff(search="old text", replace="new text")
        result = diff.apply("old text")
        assert result == "new text"

    def test_apply_with_anchor_based_diff(self) -> None:
        """Test apply() with anchor-based Diff."""
        from fabricatio_diff.rust import format_hashes

        content = "line1\nline2\nline3\nline4"
        formatted = format_hashes(content)
        lines = formatted.split("\n")

        # Get anchors for lines 2-3
        start_anchor = lines[1].split("|")[0]  # line2
        end_anchor = lines[2].split("|")[0]  # line3

        diff = Diff.from_anchors(
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            replace="middle replaced",
        )

        result = diff.apply(content)
        assert result is not None
        assert result == "line1\nmiddle replaced\nline4"

    def test_apply_with_line_range_diff(self) -> None:
        """Test apply() with line-number-based Diff."""
        content = "line1\nline2\nline3\nline4"

        diff = Diff.from_line_range(
            start=2,
            end=3,
            replace="replaced lines",
        )

        result = diff.apply(content)
        assert result is not None
        assert result == "line1\nreplaced lines\nline4"
