from typing import List

from pydantic import Field

from fabricatio.models.action import WorkFlow
from fabricatio.models.generic import Memorable, WithToDo, WithBriefing, LLMUsage


class Role[T: WorkFlow](Memorable, WithBriefing, WithToDo, LLMUsage):
    workflows: List[T] = Field(frozen=True)
    """A list of action names that the role can perform."""

    async def act(self):
        pass
