"""Correct capability module providing advanced review and validation functionality.

This module implements the Correct capability, which extends the Review functionality
to provide mechanisms for reviewing, validating, and correcting various objects and tasks
based on predefined criteria and templates.
"""

from typing import Optional, Type, Unpack, cast

from fabricatio._rust_instances import TEMPLATE_MANAGER
from fabricatio.capabilities.propose import Propose
from fabricatio.capabilities.rating import Rating
from fabricatio.config import configs
from fabricatio.journal import logger
from fabricatio.models.extra.problem import Improvement, ProblemSolutions
from fabricatio.models.generic import CensoredAble, ProposedUpdateAble, SketchedAble
from fabricatio.models.kwargs_types import (
    BestKwargs,
    CensoredCorrectKwargs,
    CorrectKwargs,
    ValidateKwargs,
)
from fabricatio.utils import ok, override_kwargs
from questionary import confirm, text
from rich import print as rprint


class Correct(Rating, Propose):
    """Correct capability for reviewing, validating, and improving objects.

    This class enhances the Review capability with specialized functionality for
    correcting and improving objects based on review feedback. It can process
    various inputs including tasks, strings, and generic objects that implement
    the required interfaces, applying corrections based on templated review processes.
    """

    async def decide_solution(
        self, problem_solutions: ProblemSolutions, **kwargs: Unpack[BestKwargs]
    ) -> ProblemSolutions:
        if (leng := len(problem_solutions.solutions)) == 0:
            logger.error(f"No solutions found in ProblemSolutions, Skip: {problem_solutions.problem}")
        if leng > 1:
            problem_solutions.solutions = await self.best(problem_solutions.solutions, **kwargs)
        return problem_solutions

    async def decide_improvement(self, improvement: Improvement, **kwargs: Unpack[BestKwargs]) -> Improvement:
        if (leng := len(improvement.problem_solutions)) == 0:
            logger.error(f"No problem_solutions found in Improvement, Skip: {improvement}")
        if leng > 1:
            for ps in improvement.problem_solutions:
                ps.solutions = await self.best(ps.solutions, **kwargs)
        return improvement

    async def fix_troubled_obj[M: SketchedAble](
        self,
        obj: M,
        problem_solutions: ProblemSolutions,
        reference: str = "",
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> Optional[M]:
        return await self.propose(
            cast("Type[M]", obj.__class__),
            TEMPLATE_MANAGER.render_template(
                configs.templates.fix_troubled_obj_template,
                {
                    "problem": problem_solutions.problem,
                    "solution": ok(
                        problem_solutions.final_solution(),
                        f"No solution found for problem: {problem_solutions.problem}",
                    ),
                    "reference": reference,
                },
            ),
            **kwargs,
        )

    async def fix_troubled_string(
        self,
        input_text: str,
        problem_solutions: ProblemSolutions,
        reference: str = "",
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[str]:
        return await self.ageneric_string(
            TEMPLATE_MANAGER.render_template(
                configs.templates.fix_troubled_string_template,
                {
                    "problem": problem_solutions.problem,
                    "solution": ok(
                        problem_solutions.final_solution(),
                        f"No solution found for problem: {problem_solutions.problem}",
                    ),
                    "reference": reference,
                    "string_to_fix": input_text,
                },
            ),
            **kwargs,
        )

    async def correct_obj[M: SketchedAble](
        self,
        obj: M,
        improvement: Improvement,
        reference: str = "",
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> Optional[M]:
        """Review and correct an object based on defined criteria and templates.

        This method first conducts a review of the given object, then uses the review results
        to generate a corrected version of the object using appropriate templates.

        Args:
            obj (M): The object to be reviewed and corrected. Must implement ProposedAble.
            improvement (Improvement): The improvement object containing the review results.
            reference (str): A reference or contextual information for the object.
            **kwargs: Review configuration parameters including criteria and review options.

        Returns:
            Optional[M]: A corrected version of the input object, or None if correction fails.

        Raises:
            TypeError: If the provided object doesn't implement Display or WithBriefing interfaces.
        """
        if not improvement.decided():
            improvement = await self.decide_improvement(improvement, **override_kwargs(kwargs, default=None))

        for ps in improvement.problem_solutions:
            fixed_obj = await self.fix_troubled_obj(obj, ps, reference, **kwargs)
            if fixed_obj is None:
                logger.error(
                    f"Failed to fix troubling obj {obj.__class__.__name__} when deal with problem: {ps.problem}",
                )
                return None
            obj = fixed_obj
        return obj

    async def correct_string(
        self, input_text: str, improvement: Improvement, reference: str = "", **kwargs: Unpack[ValidateKwargs[str]]
    ) -> Optional[str]:
        if not improvement.decided():
            improvement = await self.decide_improvement(improvement, **override_kwargs(kwargs, default=None))

        for ps in improvement.problem_solutions:
            fixed_string = await self.fix_troubled_string(input_text, ps, reference, **kwargs)
            if fixed_string is None:
                logger.error(
                    f"Failed to fix troubling string when deal with problem: {ps.problem}",
                )
                return None
            input_text = fixed_string
        return input_text

    async def censor_obj[M: CensoredAble](self, obj: M, **kwargs: Unpack[CensoredCorrectKwargs[Improvement]]) -> M:
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
        self, obj: M, **kwargs: Unpack[CorrectKwargs[Improvement]]
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
