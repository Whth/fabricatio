"""A class that represents a review result, including identified problems and solutions."""

from typing import List, Self

from fabricatio.models.generic import Display, ProposedAble, ProposedUpdateAble, WithBriefing, WithRef
from fabricatio.models.utils import ask_edit
from questionary import Choice, checkbox, text
from questionary.prompts.common import print_formatted_text as q_print
from rich import print as r_print


class ProblemSolutions(ProposedUpdateAble):
    """Represents a problem-solution pair identified during a review process.

    This class encapsulates a single problem with its corresponding potential solutions,
    providing a structured way to manage review findings.

    Attributes:
        problem (str): The problem statement identified during review.
        solutions (List[str]): A collection of potential solutions to address the problem.
    """

    problem: str
    """The problem identified in the review."""
    solutions: List[str]
    """A collection of potential solutions to address the problem."""

    def update_from_inner(self, other: Self) -> Self:
        """Update the current instance with the attributes of another instance."""
        self.solutions.clear()
        self.solutions.extend(other.solutions)
        return self

    def update_problem(self, problem: str) -> Self:
        """Update the problem description.

        Args:
            problem (str): The new problem description to replace the current one.

        Returns:
            Self: The current instance with updated problem description.
        """
        self.problem = problem
        return self

    def update_solutions(self, solutions: List[str]) -> Self:
        """Update the list of potential solutions.

        Args:
            solutions (List[str]): The new collection of solutions to replace the current ones.

        Returns:
            Self: The current instance with updated solutions.
        """
        self.solutions = solutions
        return self

    async def edit_problem(self) -> Self:
        """Interactively edit the problem description using a prompt.

        Returns:
            Self: The current instance with updated problem description.
        """
        self.problem = await text("Please edit the problem below:", default=self.problem).ask_async()
        return self

    async def edit_solutions(self) -> Self:
        """Interactively edit the list of potential solutions using a prompt.

        Returns:
            Self: The current instance with updated solutions.
        """
        q_print(self.problem, style="bold cyan")
        self.solutions = await ask_edit(self.solutions)
        return self


class ReviewResult[T](ProposedAble, Display, WithRef[T]):
    """Represents the outcome of a review process with identified problems and solutions.

    This class maintains a structured collection of problems found during a review,
    their proposed solutions, and a reference to the original reviewed object.

    Attributes:
        review_topic (str): The subject or focus area of the review.
        problem_solutions (List[ProblemSolutions]): Collection of problems identified
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
            choices=[Choice(p.problem, p, checked=True) for p in self.problem_solutions],
        ).ask_async()
        self.problem_solutions = [await p.edit_problem() for p in chosen_ones]
        if not check_solutions:
            return self

        # Choose the solutions to retain
        for to_exam in self.problem_solutions:
            to_exam.update_solutions(
                await checkbox(
                    f"Please choose the solutions you want to retain.(Default: retain all)\n\t`{to_exam.problem}`",
                    choices=[Choice(s, s, checked=True) for s in to_exam.solutions],
                ).ask_async()
            )
            await to_exam.edit_solutions()

        return self
