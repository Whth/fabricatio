"""A class representing a problem-solution pair identified during a review process."""

from itertools import chain
from typing import List, Literal, Optional, Self

from fabricatio.journal import logger
from fabricatio.models.generic import SketchedAble, WithBriefing
from fabricatio.utils import ask_edit
from questionary import Choice, checkbox, text
from rich import print as r_print


class Problem(SketchedAble, WithBriefing):
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


class Solution(SketchedAble, WithBriefing):
    """Represents a proposed solution to a problem."""

    description: str
    """Description of the solution, including a detailed description of the execution steps, and the mechanics, principle or fact."""

    execute_steps: List[str]
    """A list of steps to execute to implement the solution, which is expected to be able to finally solve the corresponding problem."""

    feasibility: Literal["low", "medium", "high"]
    """Feasibility level of the solution."""

    impact: Literal["low", "medium", "high"]
    """Impact level of the solution."""


class ProblemSolutions(SketchedAble):
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
        r_print(self.problem.display())
        string_seq = await ask_edit([s.display() for s in self.solutions])
        self.solutions = [Solution.model_validate_strings(s) for s in string_seq]
        return self

    def decided(self) -> bool:
        """Check if the improvement is decided."""
        return len(self.solutions) == 1

    def final_solution(self) -> Optional[Solution]:
        """Get the final solution."""
        if not self.decided():
            logger.error(
                f"There is more than one solution for problem {self.problem.name}, please decide which solution is eventually adopted."
            )
            return None
        return self.solutions[0]


class Improvement(SketchedAble):
    """A class representing an improvement suggestion."""

    focused_on: str
    """The focused on topic of the improvement"""

    problem_solutions: List[ProblemSolutions]
    """Collection of problems identified during review along with their potential solutions."""

    async def supervisor_check(self, check_solutions: bool = True) -> Self:
        """Perform an interactive review session to filter problems and solutions.

        Presents an interactive prompt allowing a supervisor to select which
        problems (and optionally solutions) should be retained in the final review.

        Args:
            check_solutions (bool, optional): When True, also prompts for filtering
                individual solutions for each retained problem. Defaults to False.

        Returns:
            Self: The current instance with filtered problems and solutions.
        """
        # Choose the problems to retain
        chosen_ones: List[ProblemSolutions] = await checkbox(
            "Please choose the problems you want to retain.(Default: retain all)",
            choices=[Choice(p.problem.name, p, checked=True) for p in self.problem_solutions],
        ).ask_async()
        self.problem_solutions = [await p.edit_problem() for p in chosen_ones]
        if not check_solutions:
            return self

        # Choose the solutions to retain
        for to_exam in self.problem_solutions:
            to_exam.update_solutions(
                await checkbox(
                    f"Please choose the solutions you want to retain.(Default: retain all)\n\t`{to_exam.problem}`",
                    choices=[Choice(s.name, s, checked=True) for s in to_exam.solutions],
                ).ask_async()
            )
            await to_exam.edit_solutions()

        return self

    def decided(self) -> bool:
        """Check if the improvement is decided."""
        return all(ps.decided() for ps in self.problem_solutions)

    @classmethod
    def gather(cls, *improvements: Self) -> Self:
        """Gather multiple improvements into a single instance."""
        return cls(
            focused_on="\n".join(imp.focused_on for imp in improvements),
            problem_solutions=list(chain(*(imp.problem_solutions for imp in improvements))),
        )
