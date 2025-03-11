"""A module that provides functionality to rate tasks based on a rating manual and score range."""

from typing import List, Optional, Self, Set, Unpack, cast

from fabricatio._rust_instances import TEMPLATE_MANAGER
from fabricatio.capabilities.propose import Propose
from fabricatio.capabilities.rating import GiveRating
from fabricatio.config import configs
from fabricatio.models.generic import Base, Display, ProposedAble, WithBriefing
from fabricatio.models.kwargs_types import ReviewKwargs, ValidateKwargs
from fabricatio.models.task import Task
from fabricatio.models.utils import ask_edit
from questionary import Choice, checkbox, text
from questionary import print as q_print
from rich import print as r_print


class ProblemSolutions(Base):
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


class ReviewResult[T](ProposedAble, Display):
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

    _ref: T
    """Reference to the original object that was reviewed."""

    def update_topic(self, topic: str) -> Self:
        """Update the review topic.

        Args:
            topic (str): The new topic to be associated with this review.

        Returns:
            Self: The current instance with updated review topic.
        """
        self.review_topic = topic
        return self

    def update_ref[K](self, ref: K) -> "ReviewResult[K]":
        """Update the reference to the reviewed object.

        Args:
            ref (K): The new reference object to be associated with this review.

        Returns:
            ReviewResult[K]: The current instance with updated reference type.
        """
        self._ref = ref  # pyright: ignore [reportAttributeAccessIssue]
        return cast(ReviewResult[K], self)

    def deref(self) -> T:
        """Retrieve the referenced object that was reviewed.

        Returns:
            T: The original object that was reviewed.
        """
        return self._ref

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
        if isinstance(self._ref, str):
            display = self._ref
        elif isinstance(self._ref, WithBriefing):
            display = self._ref.briefing
        elif isinstance(self._ref, Display):
            display = self._ref.display()
        else:
            raise TypeError(f"Unsupported type for review: {type(self._ref)}")
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


class Review(GiveRating, Propose):
    """Class that provides functionality to review tasks and strings using a language model.

    This class extends GiveRating and Propose capabilities to analyze content,
    identify problems, and suggest solutions based on specified criteria.

    The review process can be applied to Task objects or plain strings with
    appropriate topic and criteria.
    """

    async def review_task[T](self, task: Task[T], **kwargs: Unpack[ReviewKwargs]) -> ReviewResult[Task[T]]:
        """Review a task using specified review criteria.

        This method analyzes a task object to identify problems and propose solutions
        based on the criteria provided in kwargs.

        Args:
            task (Task[T]): The task object to be reviewed.
            **kwargs (Unpack[ReviewKwargs]): Additional keyword arguments for the review process,
                including topic and optional criteria.

        Returns:
            ReviewResult[Task[T]]: A review result containing identified problems and proposed solutions,
                with a reference to the original task.
        """
        return cast(ReviewResult[Task[T]], await self.review_obj(task, **kwargs))

    async def review_string(
        self,
        input_text: str,
        topic: str,
        criteria: Optional[Set[str]] = None,
        **kwargs: Unpack[ValidateKwargs[ReviewResult[str]]],
    ) -> ReviewResult[str]:
        """Review a string based on specified topic and criteria.

        This method analyzes a text string to identify problems and propose solutions
        based on the given topic and criteria.

        Args:
            input_text (str): The text content to be reviewed.
            topic (str): The subject topic for the review criteria.
            criteria (Optional[Set[str]], optional): A set of criteria for the review.
                If not provided, criteria will be drafted automatically. Defaults to None.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            ReviewResult[str]: A review result containing identified problems and proposed solutions,
                with a reference to the original text.
        """
        default = None
        if "default" in kwargs:
            default = kwargs.pop("default")

        criteria = criteria or (await self.draft_rating_criteria(topic, **kwargs))
        if not criteria:
            raise ValueError("No criteria provided for review.")
        manual = await self.draft_rating_manual(topic, criteria, **kwargs)

        if default is not None:
            kwargs["default"] = default
        res = await self.propose(
            ReviewResult,
            TEMPLATE_MANAGER.render_template(
                configs.templates.review_string_template,
                {"text": input_text, "topic": topic, "criteria_manual": manual},
            ),
            **kwargs,
        )
        if not res:
            raise ValueError("Failed to generate review result.")
        return res.update_ref(input_text).update_topic(topic)

    async def review_obj[M: (Display, WithBriefing)](
        self, obj: M, **kwargs: Unpack[ReviewKwargs[ReviewResult[str]]]
    ) -> ReviewResult[M]:
        """Review an object that implements Display or WithBriefing interface.

        This method extracts displayable text from the object and performs a review
        based on the criteria provided in kwargs.

        Args:
            obj (M): The object to be reviewed, which must implement either Display or WithBriefing.
            **kwargs (Unpack[ReviewKwargs]): Additional keyword arguments for the review process,
                including topic and optional criteria.

        Raises:
            TypeError: If the object does not implement Display or WithBriefing.

        Returns:
            ReviewResult[M]: A review result containing identified problems and proposed solutions,
                with a reference to the original object.
        """
        if isinstance(obj, Display):
            text = obj.display()
        elif isinstance(obj, WithBriefing):
            text = obj.briefing
        else:
            raise TypeError(f"Unsupported type for review: {type(obj)}")

        return (await self.review_string(text, **kwargs)).update_ref(obj)
