from abc import abstractmethod
from typing import Tuple

from pydantic import Field

from fabricatio.models.generic import WithBriefing


class Action(WithBriefing):
    pass

    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass


class WorkFlow(WithBriefing):
    steps: Tuple[Action, ...] = Field(default=())

    async def execute(self, *args, **kwargs):
        for step in self.steps:
            await step.execute(*args, **kwargs)
