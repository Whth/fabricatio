"""A class representing a problem-solution pair identified during a review process."""

from typing import List, Literal, Self

from fabricatio.models.generic import Display, ProposedAble, ProposedUpdateAble, WithBriefing
from fabricatio.utils import ask_edit
from pydantic import Field
from questionary import text
from questionary.prompts.common import print_formatted_text as q_print


class Problem(ProposedAble, WithBriefing, Display):
    """Represents a problem identified during review."""

    description: str
    """Description of the problem, The """

    severity: Literal["low", "medium", "high"]
    """Severity level of the problem."""

    category: str
    """Category of the problem."""

    location: str
    """Location where the problem was identified."""

    recommendation: str
    """Recommended solution or action."""


class Solution(ProposedAble, WithBriefing, Display):
    """Represents a proposed solution to a problem."""

    operation: str
    """Description or identifier of the operation."""

    feasibility: Literal["low", "medium", "high"]
    """Feasibility level of the solution."""

    impact: Literal["low", "medium", "high"]
    """Impact level of the solution."""


class ProblemSolutions(ProposedUpdateAble):
    """Represents a problem-solution pair identified during a review process."""

    problem: Problem
    """The problem identified in the review."""
    solutions: List[Solution]
    """A collection of potential solutions."""

    def update_from_inner(self, other: Self) -> Self:
        """Update the current instance with another instance's attributes."""
        self.solutions.clear()
        self.solutions.extend(other.solutions)
        return self

    def update_problem(self, problem: Problem) -> Self:
        """Update the problem description."""
        self.problem = problem
        return self

    def update_solutions(self, solutions: List[Solution]) -> Self:
        """Update the list of potential solutions."""
        self.solutions = solutions
        return self

    async def edit_problem(self) -> Self:
        """Interactively edit the problem description."""
        self.problem = Problem.model_validate_strings(
            await text("Please edit the problem below:", default=self.problem.display()).ask_async()
        )
        return self

    async def edit_solutions(self) -> Self:
        """Interactively edit the list of potential solutions."""
        q_print(self.problem.display(), style="bold cyan")
        string_seq = await ask_edit([s.display() for s in self.solutions])
        self.solutions = [Solution.model_validate_strings(s) for s in string_seq]
        return self
