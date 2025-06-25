"""Test module for the review_string method in the Review class."""

import pytest
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import ok
from fabricatio_improve.capabilities.review import Review
from fabricatio_improve.models.improve import Improvement
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_string
from fabricatio_mock.utils import install_router
from litellm import Router


class ReviewerRole(LLMTestRole, Review):
    """A test class that combines LLMTestRole and Review functionalities for testing review capabilities."""


@pytest.fixture
def router(ret_value: SketchedAble) -> Router:
    """Fixture to create a Router instance with predefined mocked responses for testing."""
    return return_model_json_string(ret_value)


@pytest.fixture
def role() -> ReviewerRole:
    """Fixture to instantiate a ReviewerRole object for testing."""
    return ReviewerRole()


@pytest.mark.parametrize(
    ("ret_value", "prompt"),
    [
        (Improvement(focused_on="some thing", problem_solutions=[]), "some thing is wrong"),
    ],
)
@pytest.mark.asyncio
async def test_review_string(router: Router, role: ReviewerRole, ret_value: SketchedAble, prompt: str) -> None:
    """Verify the correctness of the review_string method with various input combinations.

    Tests include scenarios with and without explicit criteria provided.
    """
    topic = "generic topic"

    with install_router(router):
        imp = ok(
            await role.review_string(
                prompt, topic, criteria={"some thing"}, rating_manual={"some thing": "a is bad, b is good."}
            )
        )
        assert imp.model_dump_json() == ret_value.model_dump_json()

        # Validate functionality when 'criteria' is omitted and only 'rating_manual' is provided
        imp = ok(await role.review_string(prompt, topic, rating_manual={"some thing": "a is bad, b is good."}))
        assert imp.model_dump_json() == ret_value.model_dump_json()
