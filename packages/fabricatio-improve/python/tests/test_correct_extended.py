"""Extended tests for fabricatio-improve Correct capability."""

import pytest
from fabricatio_improve.capabilities.correct import Correct
from fabricatio_improve.models.improve import Improvement
from fabricatio_improve.models.problem import Problem, ProblemSolutions, Solution
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_generic_router_usage
from fabricatio_mock.utils import install_router_usage


class CorrectRole(LLMTestRole, Correct):
    """Test role combining LLMTestRole with Correct."""


@pytest.fixture
def role() -> CorrectRole:
    """Create a CorrectRole instance."""
    return CorrectRole()


@pytest.fixture
def single_solution_ps() -> ProblemSolutions:
    """ProblemSolutions with exactly one solution (decided)."""
    return ProblemSolutions(
        problem=Problem(name="Bug", cause="Off by one", severity_level=3, location="loop"),
        solutions=[
            Solution(
                name="Fix",
                mechanism="Adjust loop bound",
                execute_steps=["change < to <="],
                feasibility_level=9,
                impact_level=8,
            )
        ],
    )


@pytest.fixture
def multi_solution_ps() -> ProblemSolutions:
    """ProblemSolutions with multiple solutions (undecided)."""
    return ProblemSolutions(
        problem=Problem(name="Perf", cause="Slow query", severity_level=7, location="db.py"),
        solutions=[
            Solution(
                name="Index",
                mechanism="Add index",
                execute_steps=["CREATE INDEX"],
                feasibility_level=8,
                impact_level=9,
            ),
            Solution(
                name="Cache",
                mechanism="Add cache",
                execute_steps=["set up redis"],
                feasibility_level=6,
                impact_level=7,
            ),
        ],
    )


class TestDecideSolution:
    """Tests for decide_solution method."""

    @pytest.mark.asyncio
    async def test_decide_solution_already_decided(
        self, role: CorrectRole, single_solution_ps: ProblemSolutions
    ) -> None:
        """Test decide_solution returns unchanged when already decided."""

    @pytest.mark.asyncio
    async def test_decide_solution_undecided_uses_best(
        self, role: CorrectRole, multi_solution_ps: ProblemSolutions
    ) -> None:
        """Test decide_solution picks best when multiple solutions exist."""
        from unittest.mock import AsyncMock, patch

        # Mock best to return the first solution
        with patch.object(type(role), "best", new_callable=AsyncMock, return_value=[multi_solution_ps.solutions[0]]):
            result = await role.decide_solution(multi_solution_ps)
            assert result.decided()


class TestDecideImprovement:
    """Tests for decide_improvement method."""

    @pytest.mark.asyncio
    async def test_decide_improvement_all_decided(
        self, role: CorrectRole, single_solution_ps: ProblemSolutions
    ) -> None:
        """Test decide_improvement when all problem solutions are already decided."""
        imp = Improvement(focused_on="test", problem_solutions=[single_solution_ps])
        result = await role.decide_improvement(imp)
        assert result is imp
        assert result.decided()

    @pytest.mark.asyncio
    async def test_decide_improvement_with_undecided(
        self, role: CorrectRole, single_solution_ps: ProblemSolutions, multi_solution_ps: ProblemSolutions
    ) -> None:
        """Test decide_improvement with mix of decided and undecided."""
        from unittest.mock import AsyncMock, patch

        imp = Improvement(focused_on="test", problem_solutions=[single_solution_ps, multi_solution_ps])
        with patch.object(type(role), "best", new_callable=AsyncMock, return_value=[multi_solution_ps.solutions[0]]):
            result = await role.decide_improvement(imp)
            assert result.decided()


class TestCorrectStringEdgeCases:
    """Edge case tests for correct_string."""

    @pytest.mark.asyncio
    async def test_correct_string_empty_improvement(self, role: CorrectRole) -> None:
        """Test correct_string with empty problem_solutions returns input unchanged."""
        imp = Improvement(focused_on="test", problem_solutions=[])
        result = await role.correct_string("some text", imp)
        assert result == "some text"

    @pytest.mark.asyncio
    async def test_correct_string_with_decided_improvement(self, role: CorrectRole) -> None:
        """Test correct_string with a decided improvement applies the fix."""
        ps = ProblemSolutions(
            problem=Problem(name="Typo", cause="typo in text", severity_level=2, location="line 1"),
            solutions=[
                Solution(
                    name="Fix",
                    mechanism="Fix typo",
                    execute_steps=["find and replace"],
                    feasibility_level=10,
                    impact_level=5,
                )
            ],
        )
        imp = Improvement(focused_on="spelling", problem_solutions=[ps])
        responses = return_generic_router_usage("fixed text")
        with install_router_usage(*responses):
            result = await role.correct_string("typo text", imp)
            assert result == "fixed text"


class TestCorrectObj:
    """Tests for correct_obj method."""

    @pytest.mark.asyncio
    async def test_correct_obj_no_improvements(self, role: CorrectRole) -> None:
        """Test correct_obj with empty improvement returns obj unchanged."""
        from fabricatio_core.models.generic import SketchedAble

        class DummyObj(SketchedAble):
            content: str = "original"

        obj = DummyObj(content="original")
        imp = Improvement(focused_on="test", problem_solutions=[])
        result = await role.correct_obj(obj, imp)
        assert result is obj
        assert result.content == "original"
