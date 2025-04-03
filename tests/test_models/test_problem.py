"""The problem module contains the Problem, Solution, ProblemSolutions, and Improvement classes."""
from unittest.mock import patch

import pytest
from fabricatio.models.extra.problem import Improvement, Problem, ProblemSolutions, Solution


@pytest.fixture
def mock_questionary():
    with (
        patch("questionary.checkbox") as mock_checkbox,
        patch("questionary.text") as mock_text,
        patch("questionary.select") as mock_select,
    ):
        yield {"checkbox": mock_checkbox, "text": mock_text, "select": mock_select}


@pytest.fixture
def mock_logger():
    with patch("fabricatio.journal.logger") as mock_logger:
        yield mock_logger


@pytest.fixture
def sample_problem():
    return Problem(
        name="Sample Problem",
        description="Sample description",
        severity="high",
        category="category",
        recommendation="Fix it",
        location="here",
    )


@pytest.fixture
def sample_solution():
    return Solution(
        name="Sample Solution",
        description="Sample steps",
        execute_steps=["Step 1", "Step 2"],
        feasibility="medium",
        impact="high",
    )


@pytest.fixture
def problem_solutions(sample_problem, sample_solution):
    return ProblemSolutions(problem=sample_problem, solutions=[sample_solution])


@pytest.fixture
def improvement(problem_solutions):
    return Improvement(focused_on="Testing", problem_solutions=[problem_solutions])


class TestProblem:
    def test_initialization(self, sample_problem):
        assert sample_problem.name == "Sample Problem"
        assert sample_problem.severity == "high"

    def test_invalid_severity(self):
        with pytest.raises(ValueError):
            Problem(severity="invalid")


class TestSolution:
    def test_initialization(self, sample_solution):
        assert len(sample_solution.execute_steps) == 2
        assert sample_solution.impact == "high"

    def test_invalid_feasibility(self):
        with pytest.raises(ValueError):
            Solution(feasibility="invalid")




class TestImprovement:
    def test_all_problems_have_solutions(self, improvement):
        assert improvement.all_problems_have_solutions() == True


    def test_gather(self, improvement):
        another_imp = Improvement(problem_solutions=[improvement.problem_solutions[0]],focused_on="")
        gathered = Improvement.gather(improvement, another_imp)
        assert len(gathered.problem_solutions) == 2

    def test_decided(self, problem_solutions, improvement,sample_problem):
        problem_solutions.solutions = [sample_problem]  # Ensure decided
        assert improvement.decided() == True
        problem_solutions.solutions = []
        assert improvement.decided() == False
        problem_solutions.solutions = [sample_problem, sample_problem]
        assert improvement.decided() == False
        