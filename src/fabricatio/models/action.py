from abc import abstractmethod
from typing import Tuple, Dict, final
from asyncio import Queue
from pydantic import Field, PrivateAttr

from fabricatio.models.generic import WithBriefing, LLMUsage


class Action[**P, R](WithBriefing, LLMUsage):

    _output: Queue[R] = PrivateAttr(default_factory=Queue)

    @abstractmethod
    async def execute(self, *args: P.args, **kwargs: P.kwargs) -> R:
        pass

    @final
    async def __call__(self, *args: P.args, **kwargs: P.kwargs):
        await self._output.put(await self.execute(*args, **kwargs))

    async def get_output(self) -> R:
        return await self._output.get()


class WorkFlow(WithBriefing, LLMUsage):
    steps: Tuple[Action, ...] = Field(default=())

    async def execute(self, *args, **kwargs):
        # TODO dispatch params to each step according to the step's signature
        for step in self.steps:
            await step.execute(*args, **kwargs)
