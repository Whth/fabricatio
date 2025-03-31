"""A module that provides functionality to rate tasks based on a rating manual and score range."""

from typing import Dict, Optional, Set, Unpack

from fabricatio.capabilities.propose import Propose
from fabricatio.capabilities.rating import Rating
from fabricatio.config import configs
from fabricatio.models.extra.problem import Improvement
from fabricatio.models.generic import Display, WithBriefing
from fabricatio.models.kwargs_types import ReviewKwargs, ValidateKwargs
from fabricatio.models.task import Task
from fabricatio.rust_instances import TEMPLATE_MANAGER
from fabricatio.utils import ok


class Review(Rating, Propose):
    """Class that provides functionality to review tasks and strings using a language model.

    This class extends GiveRating and Propose capabilities to analyze content,
    identify problems, and suggest solutions based on specified criteria.

    The review process can be applied to Task objects or plain strings with
    appropriate topic and criteria.
    """

    async def review_task[T](self, task: Task[T], **kwargs: Unpack[ReviewKwargs]) -> Optional[Improvement]:
        """Review a task using specified review criteria.

        This method analyzes a task object to identify problems and propose solutions
        based on the criteria provided in kwargs.

        Args:
            task (Task[T]): The task object to be reviewed.
            **kwargs (Unpack[ReviewKwargs]): Additional keyword arguments for the review process,
                including topic and optional criteria.

        Returns:
            Improvement[Task[T]]: A review result containing identified problems and proposed solutions,
                with a reference to the original task.
        """
        return await self.review_obj(task, **kwargs)

    async def review_string(
        self,
        input_text: str,
        topic: str,
        criteria: Optional[Set[str]] = None,
        rating_manual: Optional[Dict[str, str]] = None,
        **kwargs: Unpack[ValidateKwargs[Improvement]],
    ) -> Optional[Improvement]:
        """Review a string based on specified topic and criteria.

        This method analyzes a text string to identify problems and propose solutions
        based on the given topic and criteria.

        Args:
            input_text (str): The text content to be reviewed.
            topic (str): The subject topic for the review criteria.
            criteria (Optional[Set[str]], optional): A set of criteria for the review.
                If not provided, criteria will be drafted automatically. Defaults to None.
            rating_manual (Optional[Dict[str,str]], optional): A dictionary of rating criteria and their corresponding scores.
            **kwargs (Unpack[ValidateKwargs]): Additional keyword arguments for the LLM usage.

        Returns:
            Improvement: A review result containing identified problems and proposed solutions,
                with a reference to the original text.
        """
        default = None
        if "default" in kwargs:
            # this `default` is the default for the `propose` method
            default = kwargs.pop("default")

        criteria = ok(criteria or (await self.draft_rating_criteria(topic, **kwargs))," No criteria could be use.")
        manual = rating_manual or await self.draft_rating_manual(topic, criteria, **kwargs)

        if default is not None:
            kwargs["default"] = default
        return await self.propose(
            Improvement,
            TEMPLATE_MANAGER.render_template(
                configs.templates.review_string_template,
                {"text": input_text, "topic": topic, "criteria_manual": manual},
            ),
            **kwargs,
        )

    async def review_obj[M: (Display, WithBriefing)](self, obj: M, **kwargs: Unpack[ReviewKwargs[Improvement]]) -> Optional[Improvement]:
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
            Improvement: A review result containing identified problems and proposed solutions,
                with a reference to the original object.
        """
        if isinstance(obj, Display):
            text_to_review = obj.display()
        elif isinstance(obj, WithBriefing):
            text_to_review = obj.briefing
        else:
            raise TypeError(f"Unsupported type for review: {type(obj)}")

        return await self.review_string(text_to_review, **kwargs)
