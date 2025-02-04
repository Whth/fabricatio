from abc import abstractmethod
from typing import Tuple

from pydantic import Field

from fabricatio.models.generic import WithBriefing, LLMUsage


class Action(WithBriefing, LLMUsage):

    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass


class WorkFlow(WithBriefing, LLMUsage):
    steps: Tuple[Action, ...] = Field(default=())

    async def execute(self, *args, **kwargs):
        # TODO dispatch params to each step according to the step's signature
        for step in self.steps:
            await step.execute(*args, **kwargs)
