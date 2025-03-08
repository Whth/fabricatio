"""A module that provides functionality to rate tasks based on a rating manual and score range."""

from typing import List, Optional, Set, Unpack

from fabricatio import template_manager
from fabricatio.capabilities.propose import Propose
from fabricatio.capabilities.rating import GiveRating
from fabricatio.config import configs
from fabricatio.models.generic import Display, ProposedAble, WithBriefing
from fabricatio.models.kwargs_types import GenerateKwargs, ReviewKwargs
from fabricatio.models.task import Task
from pydantic import PrivateAttr


class ReviewResult[T](ProposedAble, Display):
    """Class that represents the result of a review.

    This class holds the problems identified in a review and their proposed solutions,
    along with a reference to the reviewed object.

    Attributes:
        existing_problems (List[str]): List of problems identified in the review.
        proposed_solutions (List[str]): List of proposed solutions to the problems identified in the review.

    Type Parameters:
        T: The type of the object being reviewed.
    """

    existing_problems: List[str]
    """List of problems identified in the review."""

    proposed_solutions: List[str]
    """List of proposed solutions to the problems identified in the review."""

    _ref: T = PrivateAttr(None)
    """Reference to the object being reviewed."""

    def update_ref[K](self, ref: K) -> "ReviewResult[K]":
        """Update the reference to the object being reviewed.

        Args:
            ref (K): The new reference to the object being reviewed.

        Returns:
            ReviewResult[K]: The updated instance of the ReviewResult class with the new reference type.
        """
        self._ref = ref
        return self

    def deref(self) -> T:
        """Dereference the object being reviewed.

        Returns:
            T: The object being reviewed.
        """
        return self._ref


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
        return await self.review_obj(task, **kwargs)

    async def review_string(
        self, text: str, topic: str, criteria: Optional[Set[str]] = None, **kwargs: Unpack[GenerateKwargs]
    ) -> ReviewResult[str]:
        """Review a string based on specified topic and criteria.

        This method analyzes a text string to identify problems and propose solutions
        based on the given topic and criteria.

        Args:
            text (str): The text content to be reviewed.
            topic (str): The subject topic for the review criteria.
            criteria (Optional[Set[str]], optional): A set of criteria for the review.
                If not provided, criteria will be drafted automatically. Defaults to None.
            **kwargs (Unpack[GenerateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            ReviewResult[str]: A review result containing identified problems and proposed solutions,
                with a reference to the original text.
        """
        criteria = criteria or (await self.draft_rating_criteria(topic))
        manual = await self.draft_rating_manual(topic, criteria)
        res: ReviewResult[str] = await self.propose(
            ReviewResult,
            template_manager.render_template(
                configs.templates.review_string_template, {"text": text, "topic": topic, "criteria_manual": manual}
            ),
            **kwargs,
        )
        return res.update_ref(text)

    async def review_obj[M: (Display, WithBriefing)](self, obj: M, **kwargs: Unpack[ReviewKwargs]) -> ReviewResult[M]:
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
