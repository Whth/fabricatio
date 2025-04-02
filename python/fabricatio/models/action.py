"""Module that contains the classes for defining and executing task workflows.

This module provides the Action and WorkFlow classes for creating structured
task execution pipelines. Actions represent atomic operations, while WorkFlows
orchestrate sequences of actions with shared context and error handling.

Classes:
    Action: Base class for defining executable actions with context management.
    WorkFlow: Manages action sequences, context propagation, and task lifecycle.
"""

import traceback
from abc import abstractmethod
from asyncio import Queue, create_task
from typing import Any, Dict, Self, Tuple, Type, Union, final

from fabricatio.journal import logger
from fabricatio.models.generic import WithBriefing
from fabricatio.models.task import Task
from fabricatio.models.usages import LLMUsage, ToolBoxUsage
from pydantic import Field, PrivateAttr

OUTPUT_KEY = "task_output"

INPUT_KEY = "task_input"


class Action(WithBriefing, LLMUsage):
    """Class that represents an action to be executed in a workflow.

    Actions are the atomic units of work in a workflow. Each action performs
    a specific operation and can modify the shared context data.
    """

    name: str = Field(default="")
    """The name of the action."""

    description: str = Field(default="")
    """The description of the action."""

    personality: str = Field(default="")
    """The personality traits or context for the action executor."""

    output_key: str = Field(default="")
    """The key used to store this action's output in the context dictionary."""

    @final
    def model_post_init(self, __context: Any) -> None:
        """Initialize the action by setting default name and description if not provided.

        Args:
            __context: The context to be used for initialization.
        """
        self.name = self.name or self.__class__.__name__
        self.description = self.description or self.__class__.__doc__ or ""

    @abstractmethod
    async def _execute(self, *_:Any, **cxt) -> Any:
        """Implement the core logic of the action.

        Args:
            **cxt: Context dictionary containing input/output data.

        Returns:
            Result of the action execution to be stored in context.
        """
        pass

    @final
    async def act(self, cxt: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action and update context.

        Args:
            cxt (Dict[str, Any]): Shared context dictionary.

        Returns:
            Updated context dictionary with new/modified entries.
        """
        ret = await self._execute(**cxt)

        if self.output_key:
            logger.debug(f"Setting output: {self.output_key}")
            cxt[self.output_key] = ret

        return cxt

    @property
    def briefing(self) -> str:
        """Generate formatted action description with personality context.

        Returns:
            Briefing text combining personality and action description.
        """
        if self.personality:
            return f"## Your personality: \n{self.personality}\n# The action you are going to perform: \n{super().briefing}"
        return f"# The action you are going to perform: \n{super().briefing}"

    def to_task_output(self)->Self:
        """Set the output key to OUTPUT_KEY and return the action instance."""
        self.output_key=OUTPUT_KEY
        return self

class WorkFlow(WithBriefing, ToolBoxUsage):
    """Manages sequences of actions to fulfill tasks.

    Handles context propagation between actions, error handling, and task lifecycle
    events like cancellation and completion.

    Attributes:
        steps (Tuple): Sequence of Action instances or classes to execute.
        task_input_key (str): Key for storing task instance in context.
        task_output_key (str): Key to retrieve final result from context.
    """

    description: str = ""
    """The description of the workflow, which describes the workflow's purpose and requirements."""

    _context: Queue[Dict[str, Any]] = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
    """Queue for storing the workflow execution context."""

    _instances: Tuple[Action, ...] = PrivateAttr(default_factory=tuple)
    """Instantiated action objects to be executed in this workflow."""

    steps: Tuple[Union[Type[Action], Action], ...] = Field(
        frozen=True,
    )
    """The sequence of actions to be executed, can be action classes or instances."""

    task_input_key: str = Field(default=INPUT_KEY)
    """Key used to store the input task in the context dictionary."""

    task_output_key: str = Field(default=OUTPUT_KEY)
    """Key used to extract the final result from the context dictionary."""

    extra_init_context: Dict[str, Any] = Field(default_factory=dict, frozen=True)
    """Additional initial context values to be included at workflow start."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the workflow by instantiating any action classes.

        Args:
            __context: The context to be used for initialization.
        """
        # Convert any action classes to instances
        self._instances = tuple(step if isinstance(step, Action) else step() for step in self.steps)

    def inject_personality(self, personality: str) -> Self:
        """Set personality for actions without existing personality.

        Args:
            personality (str): Shared personality context

        Returns:
            Workflow instance with updated actions
        """
        for action in filter(lambda a: not a.personality, self._instances):
            action.personality = personality
        return self

    async def serve(self, task: Task) -> None:
        """Execute workflow to complete given task.

        Args:
            task (Task): Task instance to be processed.

        Steps:
            1. Initialize context with task instance and extra data
            2. Execute each action sequentially
            3. Handle task cancellation and exceptions
            4. Extract final result from context
        """
        logger.info(f"Start execute workflow: {self.name}")

        await task.start()
        await self._init_context(task)

        current_action = None
        try:
            # Process each action in sequence
            for i,step in enumerate(self._instances):
                current_action = step.name
                logger.info(f"Executing step [{i}] >> {current_action}")

                # Get current context and execute action
                context = await self._context.get()
                act_task = create_task(step.act(context))
                # Handle task cancellation
                if task.is_cancelled():
                    logger.warning(f"Workflow cancelled by task: {task.name}")
                    act_task.cancel(f"Cancelled by task: {task.name}")
                    break

                # Update context with modified values
                modified_ctx = await act_task
                logger.success(f"Step [{i}] `{current_action}` execution finished.")
                if step.output_key:
                    logger.success(f"Setting action `{current_action}` output to `{step.output_key}`")
                await self._context.put(modified_ctx)

            logger.success(f"Workflow `{self.name}` execution finished.")

            # Get final context and extract result
            final_ctx = await self._context.get()
            result = final_ctx.get(self.task_output_key)

            if self.task_output_key not in final_ctx:
                logger.warning(
                    f"Task output key: `{self.task_output_key}` not found in the context, None will be returned. "
                    f"You can check if `Action.output_key` is set the same as `WorkFlow.task_output_key`."
                )

            await task.finish(result)

        except Exception as e:  # noqa: BLE001
            logger.critical(f"Error during task: {current_action} execution: {e}")
            logger.critical(traceback.format_exc())
            await task.fail()

    async def _init_context[T](self, task: Task[T]) -> None:
        """Initialize workflow execution context.

        Args:
            task (Task[T]): Task being processed

        Context includes:
            - Task instance stored under task_input_key
            - Any extra_init_context values
        """
        logger.debug(f"Initializing context for workflow: {self.name}")
        initial_context = {self.task_input_key: task, **dict(self.extra_init_context)}
        await self._context.put(initial_context)

    def steps_fallback_to_self(self) -> Self:
        """Configure all steps to use this workflow's configuration as fallback.

        Returns:
            Self: The workflow instance for method chaining.
        """
        self.hold_to(self._instances)
        return self

    def steps_supply_tools_from_self(self) -> Self:
        """Provide this workflow's tools to all steps in the workflow.

        Returns:
            Self: The workflow instance for method chaining.
        """
        self.provide_tools_to(i for i in self._instances if isinstance(i,ToolBoxUsage))
        return self

    def update_init_context(self, /, **kwargs) -> Self:
        """Update the initial context with additional key-value pairs.

        Args:
            **kwargs: Key-value pairs to add to the initial context.

        Returns:
            Self: The workflow instance for method chaining.
        """
        self.extra_init_context.update(kwargs)
        return self
