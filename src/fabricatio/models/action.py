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
        """Execute the action with the provided arguments.

        Args:
            *args: Positional arguments required for the execution.

        Returns:
            The result of the action execution.
        """
        pass

    def get_input_data(self, cxt: Dict[str, Any]) -> P.args:
        """Retrieve input data from the context based on input keys.

        Args:
            cxt: The context dictionary containing input data.

        Returns:
            A tuple of input data values corresponding to the input keys.
        """
        return tuple(cxt[k] for k in self.input_keys)

    def set_output_data(self, cxt: Dict[str, Any], output: R) -> None:
        """Set the output data in the context under the output key.

        Args:
            cxt: The context dictionary to store the output data.
            output: The output data to be stored.
        """
        cxt[self.output_key] = output

    async def act(self, cxt: Dict[str, Any]) -> None:
        """Perform the action by executing it and setting the output data.

        Args:
            cxt: The context dictionary containing input and output data.
        """
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
