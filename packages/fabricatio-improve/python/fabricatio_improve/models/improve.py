"""A module containing kwargs types for content correction and checking operations."""

from itertools import chain
from typing import Self, Unpack

from fabricatio_core.models.generic import SketchedAble

from fabricatio_improve.models.problem import ProblemSolutions


class Improvement(SketchedAble):
    """A class representing an improvement suggestion."""

    focused_on: str
    """The focused on topic of the improvement"""

    problem_solutions: list[ProblemSolutions]
    """Collection of problems identified during review along with their potential solutions."""

    def all_problems_have_solutions(self) -> bool:
        """Check if all problems have solutions."""
        return all(ps.has_solutions() for ps in self.problem_solutions)

    def decided(self) -> bool:
        """Check if the improvement is decided."""
        return all(ps.decided() for ps in self.problem_solutions)

    @classmethod
    def gather(cls, *improvements: Unpack[tuple["Improvement", ...]]) -> Self:  # noqa: UP044
        """Gather multiple improvements into a single instance."""
        return cls(
            focused_on=";".join(imp.focused_on for imp in improvements),
            problem_solutions=list(chain(*(imp.problem_solutions for imp in improvements))),
        )
