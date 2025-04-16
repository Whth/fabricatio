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
        name="t1",
        cause="Sample description",  # 修改description为cause别名
        severity_level=5,  # 修正为整数类型
        location="here",
    )


@pytest.fixture
def sample_solution():
    return Solution(
        name="t1",
        mechanism="Sample steps",  # 使用mechanism别名
        execute_steps=["Step 1", "Step 2"],
        feasibility_level=5,  # 修正为整数类型
        impact_level=8,  # 修正为整数类型
    )


@pytest.fixture
def problem_solutions(sample_problem, sample_solution):
    return ProblemSolutions(problem=sample_problem, solutions=[sample_solution])


@pytest.fixture
def improvement(problem_solutions):
    return Improvement(focused_on="Testing", problem_solutions=[problem_solutions])


class TestProblem:
    def test_initialization(self, sample_problem):
        assert sample_problem.severity_level == 5  # 修正断言为整数


class TestSolution:
    def test_initialization(self, sample_solution):
        assert sample_solution.impact_level == 8  # 修正断言为整数


class TestImprovement:
    def test_decided(self, improvement, problem_solutions, sample_solution):
        problem_solutions.solutions = [sample_solution]
        assert improvement.decided() == True
        problem_solutions.solutions = []
        assert improvement.decided() == False

    def test_all_problems_have_solutions(self, improvement, problem_solutions):
        assert improvement.all_problems_have_solutions() == True
        problem_solutions.solutions = []
        assert improvement.all_problems_have_solutions() == False
