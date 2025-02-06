from abc import abstractmethod
from typing import Tuple, Dict, Any, Type

from pydantic import Field, PrivateAttr

from fabricatio.logging import logger
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
    _context: Dict[str, Any] = PrivateAttr(default=dict)
    """ The context dictionary to be used for workflow execution."""
    _instances: Tuple[Action, ...] = PrivateAttr(...)

    steps: Tuple[Type[Action], ...] = Field(...)
    """ The steps to be executed in the workflow."""
    task_input_key: str = Field(default="input")
    """ The key of the task input data."""
    task_output_key: str = Field(default="output")
    """ The key of the task output data."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the workflow by setting fallbacks for each step.

        Args:
            __context: The context to be used for initialization.
        """

        self._instances = tuple(step() for step in self.steps)
        for step in self._instances:
            step.fallback_to(self)

    async def serve(self, task: Task) -> None:
        """Serve the task by executing the workflow steps.

        Args:
            task: The task to be served.
        """

        task.start()
        self._context[self.task_input_key] = task
        modified = self._context
        try:
            for step in self._instances:
                modified = await step.act(modified)
            task.finish(modified[self.task_output_key])
        except Exception as e:
            logger.error(f"Error during task execution: {e}")  # Log the exception
            task.fail()  # Mark the task as failed
        finally:
            self._context.clear()
