"""A class that represents the result of a review process."""

from typing import List, Self

from fabricatio.models.extra.problem import ProblemSolutions
from fabricatio.models.generic import Display, ProposedAble, WithBriefing, WithRef
from questionary import Choice, checkbox
from rich import print as r_print


class ReviewResult[T](ProposedAble, Display, WithRef[T]):
    """Represents the outcome of a review process with identified problems and solutions.

    This class maintains a structured collection of problems found during a review,
    their proposed solutions, and a reference to the original reviewed object.

    Attributes:
        review_topic (str): The subject or focus area of the review.
        problem_solutions (List[fabricatio.models.extra.problem.ProblemSolutions]): Collection of problems identified
            during review along with their potential solutions.

    Type Parameters:
        T: The type of the object being reviewed.
    """

    review_topic: str
    """The subject or focus area of the review."""

    problem_solutions: List[ProblemSolutions]
    """Collection of problems identified during review along with their potential solutions."""

    def update_topic(self, topic: str) -> Self:
        """Update the review topic.

        Args:
            topic (str): The new topic to be associated with this review.

        Returns:
            Self: The current instance with updated review topic.
        """
        self.review_topic = topic
        return self

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
        if isinstance(self.referenced, str):
            display = self.referenced
        elif isinstance(self.referenced, WithBriefing):
            display = self.referenced.briefing
        elif isinstance(self.referenced, Display):
            display = self.referenced.display()
        else:
            raise TypeError(f"Unsupported type for review: {type(self.referenced)}")
        # Choose the problems to retain
        r_print(display)
        chosen_ones: List[ProblemSolutions] = await checkbox(
            f"Please choose the problems you want to retain.(Default: retain all)\n\t`{self.review_topic}`",
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
