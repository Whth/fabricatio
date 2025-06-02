"""Module for censoring objects and strings based on provided rulesets.

This module includes the Censor class which inherits from both Correct and Check classes.
It provides methods to censor objects and strings by first checking them against a ruleset and then correcting them if necessary.
"""

from abc import ABC
from typing import Optional, Unpack

from fabricatio_capabilities.models.generic import ProposedUpdateAble
from fabricatio_capabilities.models.kwargs_types import ReferencedKwargs
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import SketchedAble
from fabricatio_core.utils import override_kwargs
from fabricatio_improve.capabilities.correct import Correct
from fabricatio_improve.models.improve import Improvement

from fabricatio_rule.capabilities.check import Check
from fabricatio_rule.models.rule import RuleSet


class Censor(Correct, Check, ABC):
    """Class to censor objects and strings based on provided rulesets.

    Inherits from both Correct and Check classes.
    Provides methods to censor objects and strings by first checking them against a ruleset and then correcting them if necessary.

    """

    async def censor_obj[M: SketchedAble](
        self, obj: M, ruleset: RuleSet, **kwargs: Unpack[ReferencedKwargs[M]]
    ) -> Optional[M]:
        """Censors an object based on the provided ruleset.

        Args:
            obj (M): The object to be censored.
            ruleset (RuleSet): The ruleset to apply for censoring.
            **kwargs: Additional keyword arguments to be passed to the check and correct methods.

        Returns:
            Optional[M]: The censored object if corrections were made, otherwise None.

        Note:
            This method first checks the object against the ruleset and then corrects it if necessary.
        """
        imp = await self.check_obj(obj, ruleset, **override_kwargs(kwargs, default=None))
        if imp is None:
            return None
        if not imp:
            logger.info(f"No improvement found for `{obj.__class__.__name__}`.")
            return obj
        logger.info(f"Generated {len(imp)} improvement(s) for `{obj.__class__.__name__}")
        return await self.correct_obj(obj, Improvement.gather(*imp), **kwargs)

    async def censor_string(
        self, input_text: str, ruleset: RuleSet, **kwargs: Unpack[ReferencedKwargs[str]]
    ) -> Optional[str]:
        """Censors a string based on the provided ruleset.

        Args:
            input_text (str): The string to be censored.
            ruleset (RuleSet): The ruleset to apply for censoring.
            **kwargs: Additional keyword arguments to be passed to the check and correct methods.

        Returns:
            Optional[str]: The censored string if corrections were made, otherwise None.

        Note:
            This method first checks the string against the ruleset and then corrects it if necessary.
        """
        imp = await self.check_string(input_text, ruleset, **override_kwargs(kwargs, default=None))
        if imp is None:
            logger.warning(f"Censor failed for string:\n{input_text}")
            return None
        if not imp:
            logger.info("No improvement found for string.")
            return input_text
        logger.info(f"Generated {len(imp)} improvement(s) for string.")
        return await self.correct_string(input_text, Improvement.gather(*imp), **kwargs)

    async def censor_obj_inplace[M: ProposedUpdateAble](
        self, obj: M, ruleset: RuleSet, **kwargs: Unpack[ReferencedKwargs[M]]
    ) -> Optional[M]:
        """Censors an object in-place based on the provided ruleset.

        This method modifies the object directly if corrections are needed.

        Args:
            obj (M): The object to be censored.
            ruleset (RuleSet): The ruleset to apply for censoring.
            **kwargs: Additional keyword arguments to be passed to the check and correct methods.

        Returns:
            Optional[M]: The censored object if corrections were made, otherwise None.

        Note:
            This method first checks the object against the ruleset and then corrects it in-place if necessary.
        """
        imp = await self.check_obj(obj, ruleset, **override_kwargs(kwargs, default=None))
        if imp is None:
            logger.warning(f"Censor failed for `{obj.__class__.__name__}`")
            return None
        if not imp:
            logger.info(f"No improvement found for `{obj.__class__.__name__}`.")
            return obj
        logger.info(f"Generated {len(imp)} improvement(s) for `{obj.__class__.__name__}")
        return await self.correct_obj_inplace(obj, improvement=Improvement.gather(*imp), **kwargs)
