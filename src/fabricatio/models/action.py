import traceback
from abc import abstractmethod
from asyncio import Queue
from typing import Any, Dict, Tuple, Type, Unpack

from pydantic import Field, PrivateAttr

from fabricatio.journal import logger
from fabricatio.models.generic import LLMUsage, WithBriefing
from fabricatio.models.task import Task


class Action(WithBriefing, LLMUsage):
    """Class that represents an action to be executed in a workflow."""

    output_key: str = Field(default="")
    """ The key of the output data."""

    @abstractmethod
    async def _execute(self, **cxt: Unpack) -> Any:
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


class WorkFlow[A: Type[Action] | Action](WithBriefing, LLMUsage):
    """Class that represents a workflow to be executed in a task."""

    _context: Queue[Dict[str, Any]] = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
    """ The context dictionary to be used for workflow execution."""

    _instances: Tuple[Action, ...] = PrivateAttr(...)

    steps: Tuple[A, ...] = Field(...)
    """ The steps to be executed in the workflow, actions or action classes."""
    task_input_key: str = Field(default="task_input")
    """ The key of the task input data."""
    task_output_key: str = Field(default="task_output")
    """ The key of the task output data."""
    extra_init_context: Dict[str, Any] = Field(default_factory=dict, frozen=True)
    """ The extra context dictionary to be used for workflow initialization."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the workflow by setting fallbacks for each step.

        Args:
            __context: The context to be used for initialization.
        """
        temp = []
        for step in self.steps:
            temp.append(step if isinstance(step, Action) else step())
        self._instances = tuple(temp)

        for step in self._instances:
            step.fallback_to(self)

    async def serve(self, task: Task) -> None:
        """Serve the task by executing the workflow steps.

        Args:
            task: The task to be served.
        """
        await task.start()
        await self._init_context()
        current_action = None
        try:
            for step in self._instances:
                logger.debug(f"Executing step: {step.name}")
                cxt = await self._context.get()
                modified_ctx = await step.act(cxt)
                await self._context.put(modified_ctx)
                current_action = step.name
            logger.info(f"Finished executing workflow: {self.name}")
            await task.finish((await self._context.get()).get(self.task_output_key, None))
        except RuntimeError as e:
            logger.error(f"Error during task: {current_action} execution: {e}")  # Log the exception
            logger.error(traceback.format_exc())  # Add this line to log the traceback
            await task.fail()  # Mark the task as failed

    async def _init_context(self) -> None:
        """Initialize the context dictionary for workflow execution."""
        logger.debug(f"Initializing context for workflow: {self.name}")
        await self._context.put({self.task_input_key: None, **dict(self.extra_init_context)})
