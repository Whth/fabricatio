"""A patch class for updating the description and name of a `WithBriefing` object, all fields within this instance will be directly copied onto the target model's field."""

from typing import Optional, Type

from fabricatio.models.extra.rule import RuleSet
from fabricatio.models.generic import Patch, WithBriefing
from pydantic import BaseModel


class BriefingPatch[T: WithBriefing](Patch[T], WithBriefing):
    """Patch class for updating the description and name of a `WithBriefing` object, all fields within this instance will be directly copied onto the target model's field."""


class RuleSetBriefingPatch(BriefingPatch[RuleSet]):
    """Patch class for updating the description and name of a `RuleSet` object, all fields within this instance will be directly copied onto the target model's field."""
    language: str
    @staticmethod
    def ref_cls() -> Optional[Type[BaseModel]]:
        """Get the reference class of the model."""
        return RuleSet
