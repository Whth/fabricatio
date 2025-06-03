"""A module containing kwargs types for content correction and checking operations."""

from itertools import chain
from typing import List, Self, Tuple, Unpack

from fabricatio_core.models.generic import SketchedAble

from fabricatio_improve.models.problem import ProblemSolutions


class Improvement(SketchedAble):
    """A class representing an improvement suggestion."""

    focused_on: str
    """The focused on topic of the improvement"""

    problem_solutions: List[ProblemSolutions]
    """Collection of problems identified during review along with their potential solutions."""

    def all_problems_have_solutions(self) -> bool:
        """Check if all problems have solutions."""
        return all(ps.has_solutions() for ps in self.problem_solutions)

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
        from questionary import Choice, checkbox

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
    def gather(cls, *improvements: Unpack[Tuple["Improvement", ...]]) -> Self:
        """Gather multiple improvements into a single instance."""
        return cls(
            focused_on=";".join(imp.focused_on for imp in improvements),
            problem_solutions=list(chain(*(imp.problem_solutions for imp in improvements))),
        )
