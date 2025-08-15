"""Tests for the diff."""

import pytest
from fabricatio_diff.capabilities.diff_edit import DiffEdit
from fabricatio_diff.models.diff import Diff
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_string
from fabricatio_mock.utils import install_router
from litellm import Router


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
def router(ret_value: Diff) -> Router:
    """Create a router fixture that returns a specific value.

    Args:
        ret_value (SketchedAble): Value to be returned by the router

    Returns:
        Router: Router instance
    """
    return return_string(ret_value.display())


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
    router: Router, role: DiffEditRole, ret_value: Diff, source: str, requirement: str, expected_result: str
) -> None:
    """Test the diff_edit method with successful cases.

    Args:
        router (Router): Mocked router fixture
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text to edit
        requirement (str): Requirement for the edit
        expected_result (str): Expected result after applying diff
    """
    with install_router(router):
        result = await role.diff_edit(source, requirement)
        assert result == expected_result


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement"),
    [
        (
            diff_factory("This is old text in a file", "This is new text in a file"),
            "This is old text in a file",
            "Replace old text with new text",
        ),
        (
            diff_factory("hello there", "world there"),
            "hello there",
            "Change greeting",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_method(router: Router, role: DiffEditRole, ret_value: Diff, source: str, requirement: str) -> None:
    """Test the diff method returns correct Diff object.

    Args:
        router (Router): Mocked router fixture
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text for diff
        requirement (str): Requirement for the diff
    """
    with install_router(router):
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
            "requirement",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_edit_no_match(
    router: Router, role: DiffEditRole, ret_value: Diff, source: str, requirement: str
) -> None:
    """Test diff_edit when search string doesn't match source.

    Args:
        router (Router): Mocked router fixture
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
    """
    with install_router(router):
        result = await role.diff_edit(source, requirement)
        # Should return None when no match is found
        assert result is None


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement", "match_precision", "expected"),
    [
        (
            diff_factory("original text here", "original content here"),
            "original text here",
            "requirement",
            0.8,
            "original content here",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_edit_with_precision(
    router: Router,
    role: DiffEditRole,
    ret_value: Diff,
    source: str,
    requirement: str,
    match_precision: float,
    expected: str,
) -> None:
    """Test diff_edit with custom match precision.

    Args:
        router (Router): Mocked router fixture
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
        match_precision (float): Match precision value
        expected (str): Expected result
    """
    with install_router(router):
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
    router: Router, role: DiffEditRole, ret_value: Diff, source: str, requirement: str, expected: str
) -> None:
    """Test diff_edit with empty source string.

    Args:
        router (Router): Mocked router fixture
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
        expected (str): Expected result
    """
    with install_router(router):
        result = await role.diff_edit(source, requirement)
        assert result == expected


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement"),
    [
        (
            Diff(search="", replace=""),
            "source text",
            "requirement",
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_method_returns_none_on_invalid_response(
    router: Router, role: DiffEditRole, ret_value: Diff, source: str, requirement: str
) -> None:
    """Test diff method returns None when LLM response is invalid.

    Args:
        router (Router): Mocked router fixture
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object (invalid)
        source (str): Source text
        requirement (str): Requirement for diff
    """
    with install_router(router):
        diff = await role.diff(source, requirement)
        # The _validator should return None for invalid diffs
        assert diff is None


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement", "expected"),
    [
        (
            diff_factory("hello world", "hi world"),
            "hello world",
            "test requirement",
            "hi world",
        ),
        (
            diff_factory("hello\nhello", "hi\nhi"),
            "hello\nhello",
            "test requirement",
            "hi\nhi",
        ),
        (
            diff_factory("exact match", "perfect fit"),
            "exact match",
            "test requirement",
            "perfect fit",
        ),
        (
            diff_factory("Case sensitive", "case sensitive"),
            "case sensitive",
            "test requirement",
            None,
        ),
    ],
)
@pytest.mark.asyncio
async def test_diff_edit_various_cases(
    router: Router, role: DiffEditRole, ret_value: Diff, source: str, requirement: str, expected: str
) -> None:
    """Test diff_edit with various search and replace scenarios.

    Args:
        router (Router): Mocked router fixture
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
        expected (str): Expected result
    """
    with install_router(router):
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
    router: Router, role: DiffEditRole, ret_value: Diff, source: str, requirement: str, expected: str
) -> None:
    """Test diff_edit with multiline text.

    Args:
        router (Router): Mocked router fixture
        role (DiffEditRole): DiffEditRole fixture
        ret_value (Diff): Expected diff object
        source (str): Source text
        requirement (str): Requirement for edit
        expected (str): Expected result
    """
    with install_router(router):
        result = await role.diff_edit(source, requirement)
        assert result == expected
