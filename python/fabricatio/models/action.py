"""Module that contains the classes for actions and workflows."""

import traceback
from abc import abstractmethod
from asyncio import Queue, create_task
from typing import Any, Dict, Self, Tuple, Type, Union, Unpack, final

from fabricatio.capabilities.review import Review
from fabricatio.capabilities.task import HandleTask, ProposeTask
from fabricatio.journal import logger
from fabricatio.models.generic import WithBriefing
from fabricatio.models.task import Task
from fabricatio.models.usages import ToolBoxUsage
from pydantic import Field, PrivateAttr


class Action(HandleTask, ProposeTask, Review):
    """Class that represents an action to be executed in a workflow."""

    name: str = Field(default="")
    """The name of the action."""
    description: str = Field(default="")
    """The description of the action."""
    personality: str = Field(default="")
    """The personality of whom the action belongs to."""
    output_key: str = Field(default="")
    """The key of the output data."""

    @final
    def model_post_init(self, __context: Any) -> None:
        """Initialize the action by setting the name if not provided.

        Args:
            __context: The context to be used for initialization.
        """
        self.name = self.name or self.__class__.__name__
        self.description = self.description or self.__class__.__doc__ or ""

    @abstractmethod
    async def _execute(self, **cxt: Unpack) -> Any:
        """Execute the action with the provided arguments.

        Args:
            **cxt: The context dictionary containing input and output data.

        Returns:
            The result of the action execution.
        """
        pass

    @final
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

    @property
    def briefing(self) -> str:
        """Return a brief description of the action."""
        if self.personality:
            return f"## Your personality: \n{self.personality}\n# The action you are going to perform: \n{super().briefing}"
        return f"# The action you are going to perform: \n{super().briefing}"


class WorkFlow(WithBriefing, ToolBoxUsage):
    """Class that represents a workflow to be executed in a task."""

    _context: Queue[Dict[str, Any]] = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
    """ The context dictionary to be used for workflow execution."""

    _instances: Tuple[Action, ...] = PrivateAttr(...)
    """ The instances of the workflow steps."""

    steps: Tuple[Union[Type[Action], Action], ...] = Field(...)
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

    def inject_personality(self, personality: str) -> Self:
        """Inject the personality of the workflow.

        Args:
            personality: The personality to be injected.

        Returns:
            Self: The instance of the workflow with the injected personality.
        """
        for a in filter(lambda action: not action.personality, self._instances):
            a.personality = personality
        return self

    async def serve(self, task: Task) -> None:
        """Serve the task by executing the workflow steps.

        Args:
            task: The task to be served.
        """
        await task.start()
        await self._init_context(task)
        current_action = None
        try:
            for step in self._instances:
                logger.debug(f"Executing step: {step.name}")
                act_task = create_task(step.act(await self._context.get()))
                if task.is_cancelled():
                    act_task.cancel(f"Cancelled by task: {task.name}")
                    break
                modified_ctx = await act_task
                await self._context.put(modified_ctx)
                current_action = step.name
            logger.info(f"Finished executing workflow: {self.name}")
            final_ctx = await self._context.get()
            if self.task_output_key not in final_ctx:
                logger.warning(
                    f"Task output key: {self.task_output_key} not found in the context, None will be returned. You can check if `Action.output_key` is set the same as `WorkFlow.task_output_key`."
                )

            await task.finish(final_ctx.get(self.task_output_key, None))
        except RuntimeError as e:
            logger.error(f"Error during task: {current_action} execution: {e}")  # Log the exception
            logger.error(traceback.format_exc())  # Add this line to log the traceback
            await task.fail()  # Mark the task as failed

    async def _init_context[T](self, task: Task[T]) -> None:
        """Initialize the context dictionary for workflow execution."""
        logger.debug(f"Initializing context for workflow: {self.name}")
        await self._context.put({self.task_input_key: task, **dict(self.extra_init_context)})

    def steps_fallback_to_self(self) -> Self:
        """Set the fallback for each step to the workflow itself."""
        self.hold_to(self._instances)
        return self

    def steps_supply_tools_from_self(self) -> Self:
        """Supply the tools from the workflow to each step."""
        self.provide_tools_to(self._instances)
        return self
