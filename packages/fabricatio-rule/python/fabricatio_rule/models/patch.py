"""A patch class for updating the description and name of a `WithBriefing` object, all fields within this instance will be directly copied onto the target model's field."""

from typing import Optional, Type

from fabricatio_capabilities.models.generic import Patch
from fabricatio_core.models.generic import WithBriefing
from pydantic import BaseModel

from fabricatio_rule.models.rule import RuleSet


class RuleSetMetadata(Patch[RuleSet], WithBriefing):
    """A patch class for updating the description and name of a `RuleSet` object, all fields within this instance will be directly copied onto the target model's field."""

    @staticmethod
    def ref_cls() -> Optional[Type[BaseModel]]:
        """Get the reference class of the model."""
        return RuleSet
