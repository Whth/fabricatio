"""Test module for the review_string method in the Review class."""

import pytest
from fabricatio_improve.capabilities.correct import Correct
from fabricatio_improve.models.improve import Improvement
from fabricatio_improve.models.problem import Problem, ProblemSolutions, Solution
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_generic_string
from fabricatio_mock.utils import install_router
from litellm import Router


class CorrectRole(LLMTestRole, Correct):
    """A test class combining LLMTestRole and Review functionalities."""


@pytest.fixture
def router(ret_value: str) -> Router:
    """Fixture to create a router instance with mocked response."""
    return return_generic_string(ret_value)


@pytest.fixture
def role() -> CorrectRole:
    """Fixture to create a ReviewerRole instance."""
    return CorrectRole()


@pytest.mark.parametrize(
    ("ret_value", "imp", "prompt"),
    [
        ("some thing is wrong", Improvement(focused_on="string", problem_solutions=[]), "some thing is wrong"),
        (
            "good string",
            Improvement(
                focused_on="string",
                problem_solutions=[
                    ProblemSolutions(
                        problem=Problem(name="string is bad", cause="", severity_level=1, location="below the line"),
                        solutions=[
                            Solution(
                                name="fix string",
                                mechanism="fix string",
                                feasibility_level=1,
                                impact_level=1,
                                execute_steps=["find the string", "fix the string", "return the string"],
                            )
                        ],
                    )
                ],
            ),
            "some thing is wrong",
        ),
    ],
)
@pytest.mark.asyncio
async def test_correct_string(router: Router, imp: Improvement, role: CorrectRole, ret_value: str, prompt: str) -> None:
    """Test the review_string functionality with different inputs."""
    with install_router(router):
        corrected = await role.correct_string(prompt, imp)
        assert corrected == ret_value
