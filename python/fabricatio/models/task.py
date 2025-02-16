"""This module defines the `Task` class, which represents a task with a status and output.

It includes methods to manage the task's lifecycle, such as starting, finishing, cancelling, and failing the task.
"""

from asyncio import Queue
from enum import Enum
from typing import Any, Iterable, List, Optional, Self, Set, Union

from fabricatio._rust_instances import template_manager
from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models.events import Event, EventLike
from fabricatio.models.generic import LLMUsage, WithBriefing, WithDependency, WithJsonExample
from fabricatio.models.tool import ToolBox
from fabricatio.parser import JsonCapture
from pydantic import Field, NonNegativeFloat, PositiveInt, PrivateAttr, ValidationError


class TaskStatus(Enum):
    """An enumeration representing the status of a task.

    Attributes:
        Pending: The task is pending.
        Running: The task is currently running.
        Finished: The task has been successfully completed.
        Failed: The task has failed.
        Cancelled: The task has been cancelled.
    """

    Pending = "pending"
    Running = "running"
    Finished = "finished"
    Failed = "failed"
    Cancelled = "cancelled"


class Task[T](WithBriefing, WithJsonExample, WithDependency):
    """A class representing a task with a status and output.

    Attributes:
        name (str): The name of the task.
        description (str): The description of the task.
        goal (str): The goal of the task.
        dependencies (List[str]): The file dependencies of the task, a list of file paths.
        namespace (List[str]): The namespace of the task, a list of namespace segment, as string.
    """

    name: str = Field(...)
    """The name of the task."""

    description: str = Field(default="")
    """The description of the task."""

    goal: str = Field(default="")
    """The goal of the task."""

    namespace: List[str] = Field(default_factory=list)
    """The namespace of the task, a list of namespace segment, as string."""

    _output: Queue = PrivateAttr(default_factory=lambda: Queue(maxsize=1))
    """The output queue of the task."""

    _status: TaskStatus = PrivateAttr(default=TaskStatus.Pending)
    """The status of the task."""

    _namespace: Event = PrivateAttr(default_factory=Event)
    """The namespace of the task as an event, which is generated from the namespace list."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the task with a namespace event."""
        self._namespace.segments.extend(self.namespace)

    def move_to(self, new_namespace: EventLike) -> Self:
        """Move the task to a new namespace.

        Args:
            new_namespace (List[str]): The new namespace to move the task to.

        Returns:
            Task: The moved instance of the `Task` class.
        """
        self.namespace = new_namespace
        self._namespace.clear().concat(new_namespace)
        return self

    @classmethod
    def simple_task(cls, name: str, goal: str, description: str) -> Self:
        """Create a simple task with a name, goal, and description.

        Args:
            name (str): The name of the task.
            goal (str): The goal of the task.
            description (str): The description of the task.

        Returns:
            Task: A new instance of the `Task` class.
        """
        return cls(name=name, goal=goal, description=description)

    def update_task(self, goal: Optional[str] = None, description: Optional[str] = None) -> Self:
        """Update the goal and description of the task.

        Args:
            goal (str, optional): The new goal of the task.
            description (str, optional): The new description of the task.

        Returns:
            Task: The updated instance of the `Task` class.
        """
        if goal:
            self.goal = goal
        if description:
            self.description = description
        return self

    async def get_output(self) -> T:
        """Get the output of the task.

        Returns:
            T: The output of the task.
        """
        logger.debug(f"Getting output for task {self.name}")
        return await self._output.get()

    def status_label(self, status: TaskStatus) -> str:
        """Return a formatted status label for the task.

        Args:
            status (TaskStatus): The status of the task.

        Returns:
            str: The formatted status label.
        """
        return self._namespace.derive(self.name).push(status.value).collapse()

    @property
    def pending_label(self) -> str:
        """Return the pending status label for the task.

        Returns:
            str: The pending status label.
        """
        return self.status_label(TaskStatus.Pending)

    @property
    def running_label(self) -> str:
        """Return the running status label for the task.

        Returns:
            str: The running status label.
        """
        return self.status_label(TaskStatus.Running)

    @property
    def finished_label(self) -> str:
        """Return the finished status label for the task.

        Returns:
            str: The finished status label.
        """
        return self.status_label(TaskStatus.Finished)

    @property
    def failed_label(self) -> str:
        """Return the failed status label for the task.

        Returns:
            str: The failed status label.
        """
        return self.status_label(TaskStatus.Failed)

    @property
    def cancelled_label(self) -> str:
        """Return the cancelled status label for the task.

        Returns:
            str: The cancelled status label.
        """
        return self.status_label(TaskStatus.Cancelled)

    async def finish(self, output: T) -> Self:
        """Mark the task as finished and set the output.

        Args:
            output (T): The output of the task.

        Returns:
            Task: The finished instance of the `Task` class.
        """
        logger.info(f"Finishing task {self.name}")
        self._status = TaskStatus.Finished
        await self._output.put(output)
        logger.debug(f"Output set for task {self.name}")
        await env.emit_async(self.finished_label, self)
        logger.debug(f"Emitted finished event for task {self.name}")
        return self

    async def start(self) -> Self:
        """Mark the task as running.

        Returns:
            Task: The running instance of the `Task` class.
        """
        logger.info(f"Starting task {self.name}")
        self._status = TaskStatus.Running
        await env.emit_async(self.running_label, self)
        return self

    async def cancel(self) -> Self:
        """Mark the task as cancelled.

        Returns:
            Task: The cancelled instance of the `Task` class.
        """
        self._status = TaskStatus.Cancelled
        await env.emit_async(self.cancelled_label, self)
        return self

    async def fail(self) -> Self:
        """Mark the task as failed.

        Returns:
            Task: The failed instance of the `Task` class.
        """
        logger.error(f"Task {self.name} failed")
        self._status = TaskStatus.Failed
        await env.emit_async(self.failed_label, self)
        return self

    async def publish(self) -> Self:
        """Publish the task to the event bus.

        Returns:
            Task: The published instance of the `Task` class
        """
        logger.info(f"Publishing task {self.name}")
        await env.emit_async(self.pending_label, self)
        return self

    async def delegate(self) -> T:
        """Delegate the task to the event bus and wait for the output.

        Returns:
            T: The output of the task
        """
        logger.info(f"Delegating task {self.name}")
        await env.emit_async(self.pending_label, self)
        return await self.get_output()

    @property
    def briefing(self) -> str:
        """Return a briefing of the task including its goal.

        Returns:
            str: The briefing of the task.
        """
        return f"{super().briefing}\n{self.goal}"


class ProposeTask(LLMUsage, WithBriefing):
    """A class that proposes a task based on a prompt."""

    async def propose(
        self,
        prompt: str,
        max_validations: PositiveInt = 2,
        model: str | None = None,
        temperature: NonNegativeFloat | None = None,
        stop: str | List[str] | None = None,
        top_p: NonNegativeFloat | None = None,
        max_tokens: PositiveInt | None = None,
        stream: bool | None = None,
        timeout: PositiveInt | None = None,
        max_retries: PositiveInt | None = None,
    ) -> Task:
        """Asynchronously proposes a task based on a given prompt and parameters.

        Parameters:
            prompt: The prompt text for proposing a task, which is a string that must be provided.
            max_validations: The maximum number of validations allowed, default is 2.
            model: The model to be used, default is None.
            temperature: The sampling temperature, default is None.
            stop: The stop sequence(s) for generation, default is None.
            top_p: The nucleus sampling parameter, default is None.
            max_tokens: The maximum number of tokens to be generated, default is None.
            stream: Whether to stream the output, default is None.
            timeout: The timeout for the operation, default is None.
            max_retries: The maximum number of retries for the operation, default is None.

        Returns:
            A Task object based on the proposal result.
        """
        assert prompt, "Prompt must be provided."

        def _validate_json(response: str) -> None | Task:
            try:
                cap = JsonCapture.capture(response)
                logger.debug(f"Response: \n{response}")
                logger.info(f"Captured JSON: \n{cap}")
                return Task.model_validate_json(cap)
            except ValidationError as e:
                logger.error(f"Failed to parse task from JSON: {e}")
                return None

        template_data = {"prompt": prompt, "json_example": Task.json_example()}
        return await self.aask_validate(
            question=template_manager.render_template("propose_task", template_data),
            validator=_validate_json,
            system_message=f"# your personal briefing: \n{self.briefing}",
            max_validations=max_validations,
            model=model,
            temperature=temperature,
            stop=stop,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=stream,
            timeout=timeout,
            max_retries=max_retries,
        )


class ToolBoxUsage(LLMUsage):
    """A class representing the usage of tools in a task."""

    toolboxes: Set[ToolBox] = Field(default_factory=set)
    """A set of toolboxes used by the instance."""

    async def choose_toolboxes(self, task: Task):
        pass

    async def choose_tool(self, task, toolbox: ToolBox | str):
        pass

    @property
    def available_toolbox_names(self) -> List[str]:
        """Return a list of available toolbox names."""
        return [toolbox.name for toolbox in self.toolboxes]

    def supply_tools_from(self, others: Union["ToolBoxUsage", Iterable["ToolBoxUsage"]]) -> Self:
        """Supplies tools from other ToolUsage instances to this instance.

        Args:
            others ("ToolUsage" | Iterable["ToolUsage"]): A single ToolUsage instance or an iterable of ToolUsage instances
                from which to take tools.

        Returns:
            Self: The current ToolUsage instance with updated tools.
        """
        if isinstance(others, ToolBoxUsage):
            others = [others]
        for other in others:
            self.toolboxes.update(other.toolboxes)
        return self

    def provide_tools_to(self, others: Union["ToolBoxUsage", Iterable["ToolBoxUsage"]]) -> Self:
        """Provides tools from this instance to other ToolUsage instances.

        Args:
            others ("ToolUsage" | Iterable["ToolUsage"]): A single ToolUsage instance or an iterable of ToolUsage instances
                to which to provide tools.

        Returns:
            Self: The current ToolUsage instance.
        """
        if isinstance(others, ToolBoxUsage):
            others = [others]
        for other in others:
            other.toolboxes.update(self.toolboxes)
        return self


class HandleTask(WithBriefing, ToolBoxUsage):
    async def handle[T](
        self,
        task: Task[T],
        max_validations: PositiveInt = 2,
        model: str | None = None,
        temperature: NonNegativeFloat | None = None,
        stop: str | List[str] | None = None,
        top_p: NonNegativeFloat | None = None,
        max_tokens: PositiveInt | None = None,
        stream: bool | None = None,
        timeout: PositiveInt | None = None,
        max_retries: PositiveInt | None = None,
    ) -> T:
        """Asynchronously handles a task based on a given task object and parameters."""
