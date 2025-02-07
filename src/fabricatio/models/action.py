import traceback
from abc import abstractmethod
from asyncio import Queue
from typing import Tuple, Dict, Any, Type

from pydantic import Field, PrivateAttr

from fabricatio.journal import logger
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

    async def act(self, cxt: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the action by executing it and setting the output data.

        Args:
            cxt: The context dictionary containing input and output data.
        """
        ret = await self._execute(**cxt)
        if self.output_key:
            logger.debug(f"Setting output: {self.output_key}")
            cxt[self.output_key] = ret
        return cxt


class WorkFlow(WithBriefing, LLMUsage):
    _context: Queue[Dict[str, Any]] = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
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

        await task.start()
        await self._context.put({self.task_input_key: task})
        current_action = None
        try:
            for step in self._instances:
                logger.debug(f"Executing step: {step.name}")
                ctx = await self._context.get()
                modified_ctx = await step.act(ctx)
                await self._context.put(modified_ctx)
                current_action = step.name
            logger.info(f"Finished executing workflow: {self.name}")
            await task.finish((await self._context.get()).get(self.task_output_key, None))
        except Exception as e:
            logger.error(f"Error during task: {current_action} execution: {e}")  # Log the exception
            logger.error(traceback.format_exc())  # Add this line to log the traceback
            await task.fail()  # Mark the task as failed
