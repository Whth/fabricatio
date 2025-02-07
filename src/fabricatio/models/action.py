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
    async def _execute(self, **cxt) -> Any:
        """Execute the action with the provided arguments.

        Args:
            **cxt: The context dictionary containing input and output data.

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
            logger.debug(f"Setting output: {self.output_key}")
            cxt[self.output_key] = ret


class WorkFlow(WithBriefing, LLMUsage):
    _context: Dict[str, Any] = PrivateAttr(default_factory=dict)
    """ The context dictionary to be used for workflow execution."""
    _instances: Tuple[Action, ...] = PrivateAttr(...)

    steps: Tuple[Type[Action], ...] = Field(...)
    """ The steps to be executed in the workflow."""
    task_input_key: str = Field(default="task_input")
    """ The key of the task input data."""
    task_output_key: str = Field(default="task_output")
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
        current_action = None
        try:
            for step in self._instances:
                logger.debug(f"Executing step: {step.name}")
                modified = await step.act(modified)
                current_action = step.name
            logger.info(f"Finished executing workflow: {self.name}")
            task.finish(modified[self.task_output_key])
        except Exception as e:
            logger.error(f"Error during task: {current_action} execution: {e}")  # Log the exception
            task.fail()  # Mark the task as failed
        finally:
            self._context.clear()
