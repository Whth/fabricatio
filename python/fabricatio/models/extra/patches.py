"""A patch class for updating the description and name of a `WithBriefing` object, all fields within this instance will be directly copied onto the target model's field."""

from typing import Optional, Type

from fabricatio.models.extra.rule import RuleSet
from fabricatio.models.generic import Language, Patch, WithBriefing
from pydantic import BaseModel


class BriefingMetadata[T: WithBriefing](Patch[T], WithBriefing):
    """A patch class for updating the description and name of a `WithBriefing` object, all fields within this instance will be directly copied onto the target model's field."""


class RuleSetMetadata(BriefingMetadata[RuleSet], Language):
    """A patch class for updating the description and name of a `RuleSet` object, all fields within this instance will be directly copied onto the target model's field."""

    @staticmethod
    def ref_cls() -> Optional[Type[BaseModel]]:
        """Get the reference class of the model."""
        return RuleSet
