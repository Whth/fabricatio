"""Tests for fabricatio-improve models and config."""

import pytest
from fabricatio_improve.config import ImproveConfig, improve_config
from fabricatio_improve.models.improve import Improvement
from fabricatio_improve.models.problem import Problem, ProblemSolutions, Solution
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestImproveConfig:
    """Tests for ImproveConfig."""

    def test_default_templates(self) -> None:
        """Test default template values."""
        cfg = ImproveConfig()
        assert cfg.review_string_template == "built-in/review_string"
        assert cfg.fix_troubled_string_template == "built-in/fix_troubled_string"
        assert cfg.fix_troubled_obj_template == "built-in/fix_troubled_obj"

    def test_custom_templates(self) -> None:
        """Test custom template values."""
        cfg = ImproveConfig(
            review_string_template="custom/review",
            fix_troubled_string_template="custom/fix_str",
            fix_troubled_obj_template="custom/fix_obj",
        )
        assert cfg.review_string_template == "custom/review"
        assert cfg.fix_troubled_string_template == "custom/fix_str"
        assert cfg.fix_troubled_obj_template == "custom/fix_obj"

    def test_improve_config_singleton(self) -> None:
        """Test singleton is ImproveConfig."""
        assert isinstance(improve_config, ImproveConfig)


# ---------------------------------------------------------------------------
# Problem model tests
# ---------------------------------------------------------------------------


class TestProblem:
    """Tests for Problem model."""

    def test_creation(self) -> None:
        """Test Problem creation with alias field."""
        p = Problem(name="Bad Code", cause="No tests", severity_level=5, location="module.py")
        assert p.name == "Bad Code"
        assert p.description == "No tests"  # alias 'cause' maps to 'description'
        assert p.severity_level == 5
        assert p.location == "module.py"

    def test_severity_boundary_zero(self) -> None:
        """Test severity_level at lower boundary."""
        p = Problem(name="P", cause="c", severity_level=0, location="loc")
        assert p.severity_level == 0

    def test_severity_boundary_ten(self) -> None:
        """Test severity_level at upper boundary."""
        p = Problem(name="P", cause="c", severity_level=10, location="loc")
        assert p.severity_level == 10

    def test_severity_out_of_range_raises(self) -> None:
        """Test severity_level validation."""
        with pytest.raises(ValidationError):
            Problem(name="P", cause="c", severity_level=11, location="loc")

    def test_severity_negative_raises(self) -> None:
        """Test negative severity_level validation."""
        with pytest.raises(ValidationError):
            Problem(name="P", cause="c", severity_level=-1, location="loc")


# ---------------------------------------------------------------------------
# Solution model tests
# ---------------------------------------------------------------------------


class TestSolution:
    """Tests for Solution model."""

    def test_creation(self) -> None:
        """Test Solution creation with alias field."""
        s = Solution(
            name="Fix",
            mechanism="Add tests",
            execute_steps=["write test", "run test", "verify"],
            feasibility_level=8,
            impact_level=7,
        )
        assert s.name == "Fix"
        assert s.description == "Add tests"  # alias 'mechanism' maps to 'description'
        assert s.execute_steps == ["write test", "run test", "verify"]
        assert s.feasibility_level == 8
        assert s.impact_level == 7

    def test_feasibility_boundary(self) -> None:
        """Test feasibility_level boundaries."""
        s = Solution(name="S", mechanism="m", execute_steps=["step"], feasibility_level=0, impact_level=10)
        assert s.feasibility_level == 0
        assert s.impact_level == 10


# ---------------------------------------------------------------------------
# ProblemSolutions model tests
# ---------------------------------------------------------------------------


class TestProblemSolutions:
    """Tests for ProblemSolutions model."""

    @pytest.fixture
    def problem(self) -> Problem:
        """Create a sample Problem."""
        return Problem(name="Issue", cause="Root cause", severity_level=5, location="here")

    @pytest.fixture
    def solution(self) -> Solution:
        """Create a sample Solution."""
        return Solution(
            name="Fix",
            mechanism="How to fix",
            execute_steps=["step1", "step2"],
            feasibility_level=8,
            impact_level=7,
        )

    @pytest.fixture
    def ps(self, problem: Problem, solution: Solution) -> ProblemSolutions:
        """Create a sample ProblemSolutions."""
        return ProblemSolutions(problem=problem, solutions=[solution])

    def test_creation(self, ps: ProblemSolutions) -> None:
        """Test ProblemSolutions creation."""
        assert ps.problem.name == "Issue"
        assert len(ps.solutions) == 1

    def test_has_solutions_true(self, ps: ProblemSolutions) -> None:
        """Test has_solutions returns True when solutions exist."""
        assert ps.has_solutions() is True

    def test_has_solutions_false(self, problem: Problem) -> None:
        """Test has_solutions returns False when no solutions."""
        ps = ProblemSolutions(problem=problem, solutions=[])
        assert ps.has_solutions() is False

    def test_decided_single_solution(self, ps: ProblemSolutions) -> None:
        """Test decided returns True with single solution."""
        assert ps.decided() is True

    def test_decided_multiple_solutions(self, problem: Problem, solution: Solution) -> None:
        """Test decided returns False with multiple solutions."""
        ps = ProblemSolutions(problem=problem, solutions=[solution, solution])
        assert ps.decided() is False

    def test_final_solution_single(self, ps: ProblemSolutions) -> None:
        """Test final_solution returns the solution when decided."""
        result = ps.final_solution()
        assert result is not None
        assert result.name == "Fix"

    def test_final_solution_multiple_not_decided(self, problem: Problem, solution: Solution) -> None:
        """Test final_solution returns None when not decided and always_use_first=False."""
        ps = ProblemSolutions(problem=problem, solutions=[solution, solution])
        assert ps.final_solution() is None

    def test_final_solution_multiple_always_use_first(self, problem: Problem, solution: Solution) -> None:
        """Test final_solution returns first when always_use_first=True."""
        ps = ProblemSolutions(problem=problem, solutions=[solution, solution])
        result = ps.final_solution(always_use_first=True)
        assert result is not None
        assert result.name == "Fix"

    def test_update_problem(self, ps: ProblemSolutions) -> None:
        """Test update_problem."""
        new_problem = Problem(name="New", cause="new cause", severity_level=3, location="there")
        ps.update_problem(new_problem)
        assert ps.problem.name == "New"

    def test_update_solutions(self, ps: ProblemSolutions, solution: Solution) -> None:
        """Test update_solutions."""
        ps.update_solutions([solution, solution])
        assert len(ps.solutions) == 2

    def test_update_from_inner(self, ps: ProblemSolutions, problem: Problem, solution: Solution) -> None:
        """Test update_from_inner replaces solutions."""
        other = ProblemSolutions(problem=problem, solutions=[solution, solution])
        ps.update_from_inner(other)
        assert len(ps.solutions) == 2


# ---------------------------------------------------------------------------
# Improvement model tests
# ---------------------------------------------------------------------------


class TestImprovement:
    """Tests for Improvement model."""

    @pytest.fixture
    def problem_solution(self) -> ProblemSolutions:
        """Create a sample ProblemSolutions."""
        return ProblemSolutions(
            problem=Problem(name="P", cause="c", severity_level=5, location="loc"),
            solutions=[
                Solution(
                    name="S", mechanism="m", execute_steps=["step"],
                    feasibility_level=8, impact_level=7,
                )
            ],
        )

    @pytest.fixture
    def improvement(self, problem_solution: ProblemSolutions) -> Improvement:
        """Create a sample Improvement."""
        return Improvement(focused_on="quality", problem_solutions=[problem_solution])

    def test_creation(self, improvement: Improvement) -> None:
        """Test Improvement creation."""
        assert improvement.focused_on == "quality"
        assert len(improvement.problem_solutions) == 1

    def test_all_problems_have_solutions_true(self, improvement: Improvement) -> None:
        """Test all_problems_have_solutions returns True."""
        assert improvement.all_problems_have_solutions() is True

    def test_all_problems_have_solutions_false(self) -> None:
        """Test all_problems_have_solutions returns False when a problem has no solutions."""
        ps_no_sol = ProblemSolutions(
            problem=Problem(name="P", cause="c", severity_level=5, location="loc"),
            solutions=[],
        )
        imp = Improvement(focused_on="test", problem_solutions=[ps_no_sol])
        assert imp.all_problems_have_solutions() is False

    def test_decided_true(self, improvement: Improvement) -> None:
        """Test decided returns True when all problems have single solutions."""
        assert improvement.decided() is True

    def test_decided_false(self) -> None:
        """Test decided returns False when a problem has multiple solutions."""
        sol = Solution(name="S", mechanism="m", execute_steps=["step"], feasibility_level=8, impact_level=7)
        ps = ProblemSolutions(
            problem=Problem(name="P", cause="c", severity_level=5, location="loc"),
            solutions=[sol, sol],
        )
        imp = Improvement(focused_on="test", problem_solutions=[ps])
        assert imp.decided() is False

    def test_gather_improvements(self, problem_solution: ProblemSolutions) -> None:
        """Test gathering multiple improvements."""
        imp1 = Improvement(focused_on="topic1", problem_solutions=[problem_solution])
        imp2 = Improvement(focused_on="topic2", problem_solutions=[problem_solution])
        combined = Improvement.gather(imp1, imp2)
        assert combined.focused_on == "topic1;topic2"
        assert len(combined.problem_solutions) == 2

    def test_gather_single_improvement(self, improvement: Improvement) -> None:
        """Test gathering a single improvement."""
        combined = Improvement.gather(improvement)
        assert combined.focused_on == "quality"
        assert len(combined.problem_solutions) == 1

    def test_model_dump(self, improvement: Improvement) -> None:
        """Test model_dump contains expected fields."""
        data = improvement.model_dump()
        assert "focused_on" in data
        assert "problem_solutions" in data
