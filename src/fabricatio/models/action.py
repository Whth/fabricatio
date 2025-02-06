from abc import abstractmethod
from typing import Tuple, Dict, Any

from pydantic import Field

from fabricatio.models.generic import WithBriefing, LLMUsage
from fabricatio.models.task import Task


class Action(WithBriefing, LLMUsage):

    output_key: str = Field(default="")
    """ The key of the output data."""

    @abstractmethod
    async def _execute(self, **kwargs) -> Any:
        """Execute the action with the provided arguments.

        Args:
            **kwargs: The arguments to be used for the action execution.

        Returns:
            The result of the action execution.
        """
        pass

    async def act(self, cxt: Dict[str, Any]) -> None:
        """Perform the action by executing it and setting the output data.

        Args:
            cxt: The context dictionary containing input and output data.
        """
        ret = await self._execute(**cxt)
        if self.output_key:
            cxt[self.output_key] = ret


class WorkFlow(WithBriefing, LLMUsage):
    steps: Tuple[Action, ...] = Field(...)
    """ The steps to be executed in the workflow."""
    _context: Dict
    task_input_key: str = Field(default="input")
    """ The key of the task input data."""
    task_output_key: str = Field(default="output")
    """ The key of the task output data."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the workflow by setting fallbacks for each step.

        Args:
            __context: The context to be used for initialization.
        """
        for step in self.steps:
            step.fallback_to(self)

    async def serve(self, task: Task) -> None:
        """Serve the task by executing the workflow steps.

        Args:
            task: The task to be served.
        """
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
