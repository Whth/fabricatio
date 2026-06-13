"""Extended tests for fabricatio-improve Review capability."""

import pytest
from fabricatio_core.models.generic import WithBriefing
from fabricatio_improve.capabilities.review import Review
from fabricatio_improve.models.improve import Improvement
from fabricatio_improve.models.problem import Problem, ProblemSolutions, Solution
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_model_json_router_usage
from fabricatio_mock.utils import install_router_usage


class ReviewerRole(LLMTestRole, Review):
    """Test role combining LLMTestRole with Review."""


@pytest.fixture
def role() -> ReviewerRole:
    """Create a ReviewerRole instance."""
    return ReviewerRole()


@pytest.fixture
def sample_improvement() -> Improvement:
    """Create a sample Improvement for testing."""
    return Improvement(
        focused_on="code quality",
        problem_solutions=[
            ProblemSolutions(
                problem=Problem(name="Naming", cause="unclear names", severity_level=4, location="main.py"),
                solutions=[
                    Solution(
                        name="Rename",
                        mechanism="Use descriptive names",
                        execute_steps=["find bad names", "rename"],
                        feasibility_level=9,
                        impact_level=6,
                    )
                ],
            )
        ],
    )


class TestReviewStringExtended:
    """Extended tests for review_string."""

    @pytest.mark.asyncio
    async def test_review_string_with_criteria_only(self, role: ReviewerRole, sample_improvement: Improvement) -> None:
        """Test review_string with criteria set but no rating_manual."""
        responses = return_model_json_router_usage(sample_improvement)
        with install_router_usage(*responses):
            result = await role.review_string("some code", "code quality", criteria={"naming", "style"})
            assert result is not None
            assert result.focused_on == "code quality"

    @pytest.mark.asyncio
    async def test_review_string_with_manual_only(self, role: ReviewerRole, sample_improvement: Improvement) -> None:
        """Test review_string with rating_manual but no criteria."""
        responses = return_model_json_router_usage(sample_improvement)
        with install_router_usage(*responses):
            result = await role.review_string(
                "some code",
                "code quality",
                rating_manual={"naming": "good naming is descriptive"},
            )
            assert result is not None


class TestReviewObj:
    """Tests for review_obj method."""

    @pytest.mark.asyncio
    async def test_review_obj_with_withbriefing(self, role: ReviewerRole, sample_improvement: Improvement) -> None:
        """Test review_obj with a WithBriefing object."""

        class BriefedObj(WithBriefing):
            content: str = "test content"

        obj = BriefedObj(name="TestObj", description="A test object")
        responses = return_model_json_router_usage(sample_improvement)
        with install_router_usage(*responses):
            result = await role.review_obj(
                obj,
                topic="code quality",
                criteria={"quality"},
                rating_manual={"quality": "good quality"},
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_review_obj_none_result(self, role: ReviewerRole) -> None:
        """Test review_obj returns None when review_string returns None."""
        from unittest.mock import AsyncMock, patch

        class BriefedObj(WithBriefing):
            content: str = "test"

        obj = BriefedObj(name="Obj", description="desc")
        with patch.object(type(role), "review_string", new_callable=AsyncMock, return_value=None):
            result = await role.review_obj(obj, topic="quality")
            assert result is None


class TestReviewTask:
    """Tests for review_task method."""

    @pytest.mark.asyncio
    async def test_review_task_delegates_to_review_obj(
        self, role: ReviewerRole, sample_improvement: Improvement
    ) -> None:
        """Test review_task delegates to review_obj."""
        from fabricatio_core.models.task import Task

        task = Task(name="TestTask", description="A task to review", requirement="do something")
        responses = return_model_json_router_usage(sample_improvement)
        with install_router_usage(*responses):
            result = await role.review_task(
                task,
                topic="task quality",
                criteria={"clarity"},
                rating_manual={"clarity": "clear requirements"},
            )
            assert result is not None
            assert isinstance(result, Improvement)
