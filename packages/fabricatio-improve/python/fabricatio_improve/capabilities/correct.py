"""A module containing the Correct capability for reviewing, validating, and improving objects."""

from abc import ABC
from asyncio import gather
from typing import Optional, Unpack

from fabricatio_capabilities.capabilities.propose import Propose
from fabricatio_capabilities.capabilities.rating import Rating
from fabricatio_capabilities.models.generic import ProposedUpdateAble
from fabricatio_capabilities.models.kwargs_types import BestKwargs
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.models.kwargs_types import (
    ValidateKwargs,
)
from fabricatio_core.rust import TEMPLATE_MANAGER
from fabricatio_core.utils import fallback_kwargs, ok, override_kwargs

from fabricatio_improve.config import improve_config
from fabricatio_improve.models.improve import Improvement
from fabricatio_improve.models.kwargs_types import CorrectKwargs
from fabricatio_improve.models.problem import ProblemSolutions


class Correct(Rating, Propose, ABC):
    """A class that provides the capability to correct objects."""

    async def decide_solution(
        self, problem_solutions: ProblemSolutions, **kwargs: Unpack[BestKwargs]
    ) -> ProblemSolutions:
        """Decide the best solution from a list of problem solutions.

        Args:
            problem_solutions (ProblemSolutions): The problem solutions to evaluate.
            **kwargs (Unpack[BestKwargs]): Additional keyword arguments for the decision process.

        Returns:
            ProblemSolutions: The problem solutions with the best solution selected.
        """
        if (leng := len(problem_solutions.solutions)) == 0:
            logger.error(f"No solutions found in ProblemSolutions, Skip: `{problem_solutions.problem.name}`")
        if leng > 1:
            logger.info(f"{leng} solutions found in Problem `{problem_solutions.problem.name}`, select the best.")
            problem_solutions.solutions = await self.best(problem_solutions.solutions, **kwargs)
        return problem_solutions

    async def decide_improvement(self, improvement: Improvement, **kwargs: Unpack[BestKwargs]) -> Improvement:
        """Decide the best solution for each problem solution in an improvement.

        Args:
            improvement (Improvement): The improvement containing problem solutions to evaluate.
            **kwargs (Unpack[BestKwargs]): Additional keyword arguments for the decision process.

        Returns:
            Improvement: The improvement with the best solutions selected for each problem solution.
        """
        if leng := len(improvement.problem_solutions):
            logger.debug(f"{leng} problem_solutions found in Improvement, decide solution for each of them.")
            await gather(
                *[
                    self.decide_solution(
                        ps,
                        **fallback_kwargs(
                            kwargs, topic=f"which solution is better to deal this problem {ps.problem.description}\n\n"
                        ),
                    )
                    for ps in improvement.problem_solutions
                ],
            )
            if any(not (violated := ps).decided() for ps in improvement.problem_solutions):
                logger.error(f"Some problem_solutions are not decided: {violated}")
            else:
                logger.success(f"All problem_solutions are decided '{improvement.focused_on}'")
        else:
            logger.error(f"No problem_solutions found in Improvement, Skip: {improvement}")
        return improvement

    async def fix_troubled_obj[M: SketchedAble](
        self,
        obj: M,
        problem_solutions: ProblemSolutions,
        reference: str = "",
        **kwargs: Unpack[ValidateKwargs[M]],
    ) -> Optional[M]:
        """Fix a troubled object based on problem solutions.

        Args:
            obj (M): The object to be fixed.
            problem_solutions (ProblemSolutions): The problem solutions to apply.
            reference (str): A reference or contextual information for the object.
            **kwargs (Unpack[ValidateKwargs[M]]): Additional keyword arguments for the validation process.

        Returns:
            Optional[M]: The fixed object, or None if fixing fails.
        """
        return await self.propose(
            obj.__class__,
            TEMPLATE_MANAGER.render_template(
                improve_config.fix_troubled_obj_template,
                {
                    "problem": problem_solutions.problem.display(),
                    "solution": ok(
                        problem_solutions.final_solution(),
                        f"{len(problem_solutions.solutions)} solution Found for `{problem_solutions.problem.name}`.",
                    ).display(),
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
        """Fix a troubled string based on problem solutions.

        Args:
            input_text (str): The string to be fixed.
            problem_solutions (ProblemSolutions): The problem solutions to apply.
            reference (str): A reference or contextual information for the string.
            **kwargs (Unpack[ValidateKwargs[str]]): Additional keyword arguments for the validation process.

        Returns:
            Optional[str]: The fixed string, or None if fixing fails.
        """
        return await self.ageneric_string(
            TEMPLATE_MANAGER.render_template(
                improve_config.fix_troubled_string_template,
                {
                    "problem": problem_solutions.problem.display(),
                    "solution": ok(
                        problem_solutions.final_solution(),
                        f"No solution found for problem: {problem_solutions.problem}",
                    ).display(),
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
            **kwargs (Unpack[ValidateKwargs[M]]): Review configuration parameters including criteria and review options.

        Returns:
            Optional[M]: A corrected version of the input object, or None if correction fails.

        Raises:
            TypeError: If the provided object doesn't implement Display or WithBriefing interfaces.
        """
        if not improvement.decided():
            logger.info(f"Improvement {improvement.focused_on} not decided, start deciding...")
            improvement = await self.decide_improvement(improvement, **override_kwargs(kwargs, default=None))

        total = len(improvement.problem_solutions)
        for idx, ps in enumerate(improvement.problem_solutions):
            logger.info(f"[{idx + 1}/{total}] Fixing {obj.__class__.__name__} for problem `{ps.problem.name}`")
            fixed_obj = await self.fix_troubled_obj(obj, ps, reference, **kwargs)
            if fixed_obj is None:
                logger.error(f"[{idx + 1}/{total}] Failed to fix problem `{ps.problem.name}`")
                return None
            obj = fixed_obj
        return obj

    async def correct_string(
        self, input_text: str, improvement: Improvement, reference: str = "", **kwargs: Unpack[ValidateKwargs[str]]
    ) -> Optional[str]:
        """Review and correct a string based on defined criteria and templates.

        This method first conducts a review of the given string, then uses the review results
        to generate a corrected version of the string using appropriate templates.

        Args:
            input_text (str): The string to be reviewed and corrected.
            improvement (Improvement): The improvement object containing the review results.
            reference (str): A reference or contextual information for the string.
            **kwargs (Unpack[ValidateKwargs[str]]): Review configuration parameters including criteria and review options.

        Returns:
            Optional[str]: A corrected version of the input string, or None if correction fails.
        """
        if not improvement.decided():
            logger.info(f"Improvement {improvement.focused_on} not decided, start deciding...")

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

    async def correct_obj_inplace[M: ProposedUpdateAble](
        self, obj: M, **kwargs: Unpack[CorrectKwargs[M]]
    ) -> Optional[M]:
        """Correct an object in place based on defined criteria and templates.

        Args:
            obj (M): The object to be corrected.
            **kwargs (Unpack[CorrectKwargs[M]]): Additional keyword arguments for the correction process.

        Returns:
            Optional[M]: The corrected object, or None if correction fails.
        """
        corrected_obj = await self.correct_obj(obj, **kwargs)
        if corrected_obj is None:
            return corrected_obj
        obj.update_from(corrected_obj)
        return obj
