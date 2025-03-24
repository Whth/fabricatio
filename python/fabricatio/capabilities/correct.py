"""Correct capability module providing advanced review and validation functionality.

This module implements the Correct capability, which extends the Review functionality
to provide mechanisms for reviewing, validating, and correcting various objects and tasks
based on predefined criteria and templates.
"""

from typing import Optional, Unpack, cast

from fabricatio._rust_instances import TEMPLATE_MANAGER
from fabricatio.capabilities.review import Review, ReviewResult
from fabricatio.config import configs
from fabricatio.models.generic import CensoredAble, Display, ProposedAble, ProposedUpdateAble, WithBriefing
from fabricatio.models.kwargs_types import CensoredCorrectKwargs, CorrectKwargs, ReviewKwargs
from fabricatio.models.task import Task
from questionary import confirm, text
from rich import print as rprint


class Correct(Review):
    """Correct capability for reviewing, validating, and improving objects.

    This class enhances the Review capability with specialized functionality for
    correcting and improving objects based on review feedback. It can process
    various inputs including tasks, strings, and generic objects that implement
    the required interfaces, applying corrections based on templated review processes.
    """

    async def correct_obj[M: ProposedAble](
        self,
        obj: M,
        reference: str = "",
        supervisor_check: bool = True,
        **kwargs: Unpack[ReviewKwargs[ReviewResult[str]]],
    ) -> Optional[M]:
        """Review and correct an object based on defined criteria and templates.

        This method first conducts a review of the given object, then uses the review results
        to generate a corrected version of the object using appropriate templates.

        Args:
            obj (M): The object to be reviewed and corrected. Must implement ProposedAble.
            reference (str): A reference or contextual information for the object.
            supervisor_check (bool, optional): Whether to perform a supervisor check on the review results. Defaults to True.
            **kwargs: Review configuration parameters including criteria and review options.

        Returns:
            Optional[M]: A corrected version of the input object, or None if correction fails.

        Raises:
            TypeError: If the provided object doesn't implement Display or WithBriefing interfaces.
        """
        if not isinstance(obj, (Display, WithBriefing)):
            raise TypeError(f"Expected Display or WithBriefing, got {type(obj)}")

        review_res = await self.review_obj(obj, **kwargs)
        if supervisor_check:
            await review_res.supervisor_check()
        if "default" in kwargs:
            cast("ReviewKwargs[None]", kwargs)["default"] = None
        return await self.propose(
            obj.__class__,
            TEMPLATE_MANAGER.render_template(
                configs.templates.correct_template,
                {
                    "content": f"{(reference + '\n\nAbove is referencing material') if reference else ''}{obj.display() if isinstance(obj, Display) else obj.briefing}",
                    "review": review_res.display(),
                },
            ),
            **kwargs,
        )

    async def correct_string(
        self, input_text: str, supervisor_check: bool = True, **kwargs: Unpack[ReviewKwargs[ReviewResult[str]]]
    ) -> Optional[str]:
        """Review and correct a string based on defined criteria and templates.

        This method applies the review process to the input text and generates
        a corrected version based on the review results.

        Args:
            input_text (str): The text content to be reviewed and corrected.
            supervisor_check (bool, optional): Whether to perform a supervisor check on the review results. Defaults to True.
            **kwargs: Review configuration parameters including criteria and review options.

        Returns:
            Optional[str]: The corrected text content, or None if correction fails.
        """
        review_res = await self.review_string(input_text, **kwargs)
        if supervisor_check:
            await review_res.supervisor_check()

        if "default" in kwargs:
            cast("ReviewKwargs[None]", kwargs)["default"] = None
        return await self.ageneric_string(
            TEMPLATE_MANAGER.render_template(
                configs.templates.correct_template, {"content": input_text, "review": review_res.display()}
            ),
            **kwargs,
        )

    async def correct_task[T](
        self, task: Task[T], **kwargs: Unpack[CorrectKwargs[ReviewResult[str]]]
    ) -> Optional[Task[T]]:
        """Review and correct a task object based on defined criteria.

        This is a specialized version of correct_obj specifically for Task objects,
        applying the same review and correction process to task definitions.

        Args:
            task (Task[T]): The task to be reviewed and corrected.
            **kwargs: Review configuration parameters including criteria and review options.

        Returns:
            Optional[Task[T]]: The corrected task, or None if correction fails.
        """
        return await self.correct_obj(task, **kwargs)

    async def censor_obj[M: CensoredAble](
        self, obj: M, **kwargs: Unpack[CensoredCorrectKwargs[ReviewResult[str]]]
    ) -> M:
        """Censor and correct an object based on defined criteria and templates.

        Args:
            obj (M): The object to be reviewed and corrected.
            **kwargs (Unpack[CensoredCorrectKwargs]): Additional keyword

        Returns:
            M: The censored and corrected object.
        """
        last_modified_obj = obj
        modified_obj = None
        rprint(obj.finalized_dump())
        while await confirm("Begin to correct obj above with human censorship?").ask_async():
            while (topic := await text("What is the topic of the obj reviewing?").ask_async()) is not None and topic:
                ...
            if (
                modified_obj := await self.correct_obj(
                    last_modified_obj,
                    topic=topic,
                    **kwargs,
                )
            ) is None:
                break
            last_modified_obj = modified_obj
            rprint(last_modified_obj.finalized_dump())
        return modified_obj or last_modified_obj

    async def correct_obj_inplace[M: ProposedUpdateAble](
        self, obj: M, **kwargs: Unpack[CorrectKwargs[ReviewResult[str]]]
    ) -> Optional[M]:
        """Correct an object in place based on defined criteria and templates.

        Args:
            obj (M): The object to be corrected.
            **kwargs (Unpack[CensoredCorrectKwargs]): Additional keyword arguments for the correction process.

        Returns:
            Optional[M]: The corrected object, or None if correction fails.
        """
        corrected_obj = await self.correct_obj(obj, **kwargs)
        if corrected_obj is None:
            return corrected_obj
        obj.update_from(corrected_obj)
        return obj
