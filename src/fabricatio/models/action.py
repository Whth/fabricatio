from abc import abstractmethod
from typing import Tuple, Dict, Any

from pydantic import Field

from fabricatio.models.generic import WithBriefing, LLMUsage
from fabricatio.models.task import Task


class Action[**P, R](WithBriefing, LLMUsage):
    input_keys: Tuple[str, ...] = Field(default_factory=tuple)
    """ The keys of the input data."""
    output_key: str = Field(default="")
    """ The key of the output data."""

    @abstractmethod
    async def execute(self, *args: P.args) -> R:
        pass

    def get_input_data(self, cxt: Dict[str, Any]) -> P.args:
        return tuple(cxt[k] for k in self.input_keys)

    def set_output_data(self, cxt: Dict[str, Any], output: R) -> None:
        cxt[self.output_key] = output

    async def act(self, cxt: Dict[str, Any]) -> None:
        self.set_output_data(cxt, await self.execute(*self.get_input_data(cxt)))


class WorkFlow(WithBriefing, LLMUsage):
    steps: Tuple[Action, ...] = Field(...)
    """ The steps to be executed in the workflow."""
    _context: Dict
    task_input_key: str = Field(default="input")
    """ The key of the task input data."""
    task_output_key: str = Field(default="output")
    """ The key of the task output data."""

    def model_post_init(self, __context: Any) -> None:
        for step in self.steps:
            step.fallback_to(self)

    async def serve(self, task: Task) -> None:
        task.start()
        try:
            self._context[self.task_input_key] = task
            modified = self._context
            for step in self.steps:
                modified = await step.act(modified)
        except Exception:
            task.fail()
            return
        task.finish(modified[self.task_output_key])
        self._context.clear()
