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
from typing import Any, ClassVar, Dict, Generator, Self, Sequence, Tuple, Type, Union, final

from pydantic import Field, PrivateAttr

from fabricatio_core.journal import logger
from fabricatio_core.models.generic import WithBriefing
from fabricatio_core.models.task import Task
from fabricatio_core.utils import override_kwargs

OUTPUT_KEY = "task_output"

INPUT_KEY = "task_input"


class Action(WithBriefing):
    """Class that represents an action to be executed in a workflow.

    Actions are the atomic units of work in a workflow. Each action performs
    a specific operation and can modify the shared context data.
    """

    ctx_override: ClassVar[bool] = False
    """Whether to override the instance attr by the context variable."""

    name: str = Field(default="")
    """The name of the action."""

    description: str = Field(default="")
    """The description of the action."""

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
    async def _execute(self, *_: Any, **cxt) -> Any:
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

    def to_task_output(self, to: Union[str, "WorkFlow"] = OUTPUT_KEY) -> Self:
        """Set the output key to OUTPUT_KEY and return the action instance."""
        self.output_key = to.task_output_key if isinstance(to, WorkFlow) else to
        return self


class WorkFlow(WithBriefing):
    """Manages sequences of actions to fulfill tasks.

    Handles context propagation between actions, error handling, and task lifecycle
    events like cancellation and completion.
    """

    name: str = "WorkFlow"
    """The name of the workflow, which is used to identify and describe the workflow."""
    description: str = ""
    """The description of the workflow, which describes the workflow's purpose and requirements."""

    _context: Queue[Dict[str, Any]] = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
    """Queue for storing the workflow execution context."""

    _instances: Tuple[Action, ...] = PrivateAttr(default_factory=tuple)
    """Instantiated action objects to be executed in this workflow."""

    steps: Sequence[Union[Type[Action], Action]] = Field(frozen=True)
    """The sequence of actions to be executed, can be action classes or instances."""

    task_input_key: ClassVar[str] = INPUT_KEY
    """Key used to store the input task in the context dictionary."""

    task_output_key: ClassVar[str] = OUTPUT_KEY
    """Key used to extract the final result from the context dictionary."""

    extra_init_context: Dict[str, Any] = Field(default_factory=dict, frozen=True)
    """Additional initial context values to be included at workflow start."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the workflow by instantiating any action classes.

        Args:
            __context: The context to be used for initialization.

        """
        self.name = self.name or self.__class__.__name__
        # Convert any action classes to instances
        self._instances = tuple(step if isinstance(step, Action) else step() for step in self.steps)

    def iter_actions(self) -> Generator[Action, None, None]:
        """Iterate over action instances."""
        yield from self._instances

    def override_action_variable(self, action: Action, ctx: Dict[str, Any]) -> Self:
        """Override action variable with context values."""
        if action.ctx_override:
            for k, v in ctx.items():
                if hasattr(action, k):
                    setattr(action, k, v)

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
            for i, step in enumerate(self._instances):
                logger.info(f"Executing step [{i}] >> {(current_action := step.name)}")

                # Get current context and execute action
                context = await self._context.get()

                self.override_action_variable(step, context)
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
        ctx = override_kwargs(self.extra_init_context, **task.extra_init_context)
        if self.task_input_key in ctx:
            raise ValueError(
                f"Task input key: `{self.task_input_key}`, which is reserved, is already set in the init context"
            )

        await self._context.put({self.task_input_key: task, **ctx})

    def update_init_context(self, /, **kwargs) -> Self:
        """Update the initial context with additional key-value pairs.

        Args:
            **kwargs: Key-value pairs to add to the initial context.

        Returns:
            Self: The workflow instance for method chaining.
        """
        self.extra_init_context.update(kwargs)
        return self
