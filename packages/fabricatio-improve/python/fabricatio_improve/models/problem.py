"""A class representing a problem-solution pair identified during a review process."""

from typing import Any, List, Optional, Self

from fabricatio_core.journal import logger
from fabricatio_core.models.generic import SketchedAble, WithBriefing
from fabricatio_core.utils import ask_edit
from pydantic import Field
from rich import print as r_print


class Problem(SketchedAble, WithBriefing):
    """Represents a problem identified during review."""

    description: str = Field(alias="cause")
    """The cause of the problem, including the root cause, the context, and the impact, make detailed enough for engineer to understand the problem and its impact."""

    severity_level: int = Field(ge=0, le=10)
    """Severity level of the problem, which is a number between 0 and 10, 0 means the problem is not severe, 10 means the problem is extremely severe."""

    location: str
    """Location where the problem was identified."""


class Solution(SketchedAble, WithBriefing):
    """Represents a proposed solution to a problem."""

    description: str = Field(alias="mechanism")
    """Description of the solution, including a detailed description of the execution steps, and the mechanics, principle or fact."""

    execute_steps: List[str]
    """A list of steps to execute to implement the solution, which is expected to be able to finally solve the corresponding problem, and which should be an Idiot-proof tutorial."""

    feasibility_level: int = Field(ge=0, le=10)
    """Feasibility level of the solution, which is a number between 0 and 10, 0 means the solution is not feasible, 10 means the solution is complete feasible."""

    impact_level: int = Field(ge=0, le=10)
    """Impact level of the solution, which is a number between 0 and 10, 0 means the solution is not impactful, 10 means the solution is extremely impactful."""


class ProblemSolutions(SketchedAble):
    """Represents a problem-solution pair identified during a review process."""

    problem: Problem
    """The problem identified in the review."""
    solutions: List[Solution]
    """A collection of potential solutions, spread the thought, add more solution as possible.Do not leave this as blank"""

    def model_post_init(self, context: Any, /) -> None:
        """Initialize the problem-solution pair with a problem and a list of solutions."""
        if len(self.solutions) == 0:
            logger.warning(f"No solution found for problem {self.problem.name}, please add more solutions manually.")

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

    def has_solutions(self) -> bool:
        """Check if the problem-solution pair has any solutions."""
        return len(self.solutions) > 0

    async def edit_problem(self) -> Self:
        """Interactively edit the problem description."""
        from questionary import text

        """Interactively edit the problem description."""
        self.problem = Problem.model_validate_strings(
            await text("Please edit the problem below:", default=self.problem.display()).ask_async()
        )
        return self

    async def edit_solutions(self) -> Self:
        """Interactively edit the list of potential solutions."""
        r_print(self.problem.display())
        string_seq = await ask_edit([s.display() for s in self.solutions])
        self.solutions = [Solution.model_validate_strings(s) for s in string_seq]
        return self

    def decided(self) -> bool:
        """Check if the improvement is decided."""
        return len(self.solutions) == 1

    def final_solution(self, always_use_first: bool = False) -> Optional[Solution]:
        """Get the final solution."""
        if not always_use_first and not self.decided():
            logger.error(
                f"There is {len(self.solutions)} solutions for problem {self.problem.name}, please decide which solution is eventually adopted."
            )
            return None
        return self.solutions[0]
