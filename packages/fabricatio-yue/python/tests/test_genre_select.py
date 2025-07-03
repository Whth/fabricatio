"""Unit tests for genre selection functionality."""

from typing import List

import pytest
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_json_obj_string
from fabricatio_mock.utils import install_router
from fabricatio_yue.capabilities.genre import SelectGenre
from fabricatio_yue.config import yue_config
from litellm import Router
from pydantic import JsonValue


class SelectGenreRole(LLMTestRole, SelectGenre):
    """Role class combining LLMTestRole and SelectGenre capabilities."""


@pytest.fixture
def mock_router(ret_value: List[JsonValue]) -> Router:
    """Fixture to create a mocked router with predefined responses.

    Args:
        ret_value: The list of JSON values to be returned by the mocked router.

    Returns:
        A configured Router object with mocked behavior.
    """
    return return_json_obj_string(ret_value)


@pytest.fixture(autouse=True)
def role() -> SelectGenreRole:
    """Fixture to instantiate a SelectGenreRole object.

    Returns:
        An instance of SelectGenreRole for testing purposes.
    """
    return SelectGenreRole()


@pytest.mark.parametrize(
    ("requirement", "genre_classifier", "available_genres", "ret_value"),
    [
        ("upbeat party music", "dance", ["house", "techno", "disco"], ["house", "techno"]),
        ("slow romantic song", "ballad", ["pop", "rock", "classical"], ["pop", "classical"]),
    ],
)
@pytest.mark.asyncio
async def test_select_genre(
    mock_router: Router,
    requirement: str,
    genre_classifier: str,
    available_genres: List[str],
    ret_value: List[str],
    role: SelectGenreRole,
) -> None:
    """Test genre selection based on a single requirement.

    Verifies that the selected genres are valid and respect the constraints.
    """
    with install_router(mock_router):
        result = await role.select_genre(requirement, genre_classifier, available_genres)
        assert isinstance(result, list), "Result should be a list."
        assert all(genre in available_genres for genre in result), "Selected genres must belong to available genres."
        assert len(result) <= len(available_genres), "Cannot select more genres than available."

        # Test validation with a limit parameter
        result_with_limit = await role.select_genre(requirement, genre_classifier, available_genres, k=len(ret_value))
        assert isinstance(result_with_limit, list), "Result with limit should be a list."
        assert len(result_with_limit) <= len(ret_value), "Max items parameter not respected."


genres = ["house", "techno", "disco", "pop", "ambient"]


@pytest.mark.parametrize(
    ("requirements_list", "genre_classifier", "ret_value", "available_genres"),
    [
        (["upbeat party music", "slow romantic song"], "dance", ["house"], genres),
        (["epic orchestral track", "calm ambient", "slow romantic song"], "cinematic", ["pop"], genres),
    ],
)
@pytest.mark.asyncio
async def test_select_genre_with_multiple_requirements(
    mock_router: Router,
    requirements_list: List[str],
    genre_classifier: str,
    role: SelectGenreRole,
    available_genres: List[str],
) -> None:
    """Test genre selection with multiple requirements.

    Ensures that each requirement returns a valid list of genres.
    """
    with install_router(mock_router):
        result = await role.select_genre(requirements_list, genre_classifier, available_genres)
        assert isinstance(result, list), "Result should be a list."
        assert len(result) == len(requirements_list), "Should return one genre list per requirement."
        assert all(isinstance(sub_result, list) for sub_result in result), "Each entry should be a list."

        for sub_result in result:
            assert all(genre in available_genres for genre in sub_result), (
                "Selected genres must belong to available genres."
            )


@pytest.mark.parametrize(
    ("requirement", "ret_value", "k"),
    [
        # Simple case with one valid genre in a category
        ("upbeat party music", ["house", "techno", "edm", "synthwave"], 4),
        # Case where some categories may return None
        ("slow romantic song", ["pop", "classical", "lofi"], 3),
    ],
)
@pytest.mark.asyncio
async def test_gather_genres_single_requirement(
    mock_router: Router, role: SelectGenreRole, requirement: str, ret_value: List[str], k: int
) -> None:
    """Test gathering genres from all categories for a single requirement.

    Validates the structure and length of the result.
    """
    with install_router(mock_router):
        result = await role.gather_genres(requirement, k=k)
        assert isinstance(result, list if ret_value is not None else type(None)), (
            f"Expected type {list if ret_value else type(None)} but got {type(result)}."
        )
        assert len(result) == k * len(yue_config.genre.keys()), "Result should match the expected length."


@pytest.mark.parametrize(
    ("requirements_list", "ret_value", "k"),
    [
        (["upbeat party music", "slow romantic song"], ["house", "techno", "pop", "classical"], 4),
        (["epic orchestral track", "calm ambient", "slow romantic song"], ["cinematic", "ambient", "pop"], 3),
    ],
)
@pytest.mark.asyncio
async def test_gather_genres_multiple_requirements(
    mock_router: Router,
    role: SelectGenreRole,
    requirements_list: List[str],
    ret_value: List[str],
    k: int,
) -> None:
    """Test gathering genres from all categories for multiple requirements.

    Ensures that each requirement returns a valid list of genres or None.
    """
    with install_router(mock_router):
        result = await role.gather_genres(requirements_list, k=k)
        assert isinstance(result, list), "Result should be a list."
        assert len(result) == len(requirements_list), "Should return one genre list per requirement."
        assert all(isinstance(sub_result, (list, type(None))) for sub_result in result), (
            "Each entry should be either a list or None."
        )

        # Verify the expected number of genres per category
        expected_genres_per_req = k * len(yue_config.genre.keys())
        for sub_result in result:
            if sub_result is not None:
                assert len(sub_result) == expected_genres_per_req, (
                    f"Each requirement should return {expected_genres_per_req} genres."
                )
