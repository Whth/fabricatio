"""Module for censoring objects and strings based on provided rulesets.

This module includes the Censor class which inherits from both Correct and Check classes.
It provides methods to censor objects and strings by first checking them against a ruleset and then correcting them if necessary.
"""

from typing import Optional, Unpack

from fabricatio.capabilities.check import Check
from fabricatio.capabilities.correct import Correct
from fabricatio.models.extra.rule import RuleSet
from fabricatio.models.generic import ProposedUpdateAble, SketchedAble
from fabricatio.models.kwargs_types import ReferencedKwargs
from fabricatio.utils import override_kwargs


class Censor(Correct, Check):
    """Class to censor objects and strings based on provided rulesets.

    Inherits from both Correct and Check classes.
    Provides methods to censor objects and strings by first checking them against a ruleset and then correcting them if necessary.

    Attributes:
        ruleset (RuleSet): The ruleset to be used for censoring.
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
            return imp
        return await self.correct_obj(obj, imp, **kwargs)

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
            return imp
        return await self.correct_string(input_text, imp, **kwargs)

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
            return imp
        return await self.correct_obj_inplace(obj, improvement=imp, **kwargs)
