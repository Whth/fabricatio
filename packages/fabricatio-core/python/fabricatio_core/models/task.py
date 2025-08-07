"""This module defines the `Task` class, which represents a task with a status and output.

It includes methods to manage the task's lifecycle, such as starting, finishing, cancelling, and failing the task.
"""

from asyncio import Queue, run
from functools import cached_property
from typing import Dict, List, Optional, Self, Union

from pydantic import Field, PrivateAttr

from fabricatio_core.emitter import EMITTER
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import ProposedAble, WithBriefing, WithDependency
from fabricatio_core.rust import CONFIG, TEMPLATE_MANAGER, Event, TaskStatus

type NameSpace = Union[str, List[str]]


class Task[T](WithBriefing, ProposedAble, WithDependency):
    """A class representing a task with status management and output handling."""

    goals: List[str] = Field(default_factory=list)
    """Objectives the task aims to achieve."""

    description: str = Field(default="")
    """Detailed explanation of the task with 5W1H rule."""

    name: str = Field(...)
    """Concise and descriptive name of the task."""

    namespace: List[str] = Field(default_factory=list)
    """Segments indicating where the task will be sent. Using ['work'] as namespace and `::` as sep results in `work::task_name::Pending` when the task submitted."""

    dependencies: List[str] = Field(default_factory=list)
    """File paths needed to complete the task."""

    _output: Queue[T | None] = PrivateAttr(default_factory=Queue)
    """The output queue of the task."""

    _status: TaskStatus = PrivateAttr(default=TaskStatus.Pending)
    """The status of the task."""

    _extra_init_context: Dict = PrivateAttr(default_factory=dict)
    """Extra initialization context for the task, which is designed to override the one of the Workflow."""

    @property
    def extra_init_context(self) -> Dict:
        """Extra initialization context for the task, which is designed to override the one of the Workflow."""
        return self._extra_init_context

    def update_init_context(self, /, **kwargs) -> Self:
        """Update the extra initialization context for the task."""
        self.extra_init_context.update(kwargs)
        return self

    def move_to(self, new_namespace: NameSpace) -> Self:
        """Move the task to a new namespace.

        Args:
            new_namespace (str|List[str]): The new namespace to move the task to.

        Returns:
            Task: The moved instance of the `Task` class

        Example:
            .. code-block:: python

                task = Task(name="example_task", namespace=["example"]).move_to("work")
                assert task.namespace == ["work"]
        """
        logger.debug(f"Moving task `{self.name}` to `{new_namespace}`")
        self.namespace = new_namespace if isinstance(new_namespace, list) else [new_namespace]
        return self

    def update_task(self, *, goal: Optional[List[str] | str] = None, description: Optional[str] = None) -> Self:
        """Update the goal and description of the task.

        Args:
            goal (str|List[str], optional): The new goal of the task.
            description (str, optional): The new description of the task.

        Returns:
            Task: The updated instance of the `Task` class.

        Example:
            .. code-block:: python

                # Update both goal and description
                task = Task(name="example_task", goals=["old_goal"], description="old description")
                task.update_task(goal="new_goal", description="new description")
                assert task.goals == ["new_goal"]
                assert task.description == "new description"

                # Update only the goal with a single string
                task = Task(name="example_task", goals=["old_goal"])
                task.update_task(goal="new_goal")
                assert task.goals == ["new_goal"]

                # Update goal with a list of strings
                task = Task(name="example_task", goals=["old_goal"])
                task.update_task(goal=["new_goal1", "new_goal2"])
                assert task.goals == ["new_goal1", "new_goal2"]

                # Update only the description
                task = Task(name="example_task", description="old description")
                task.update_task(description="new description")
                assert task.description == "new description"


        """
        if goal:
            self.goals = goal if isinstance(goal, list) else [goal]
        if description:
            self.description = description
        return self

    async def get_output(self) -> T | None:
        """Get the output of the task.

        Returns:
            T: The output of the task.

        Example:
            .. code-block:: python

                # Test basic output retrieval
                task = Task(name="output_task")
                await task.finish("success")
                assert await task.get_output() == "success"

                # Test output retrieval with multiple get calls
                task2 = Task(name="multi_get_task")
                await task2.finish(42)
                assert await task2.get_output() == 42
                # Second get should return same value
                assert await task2.get_output() == 42

                # Test output retrieval for cancelled task
                task3 = Task(name="cancelled_task")
                await task3.cancel()
                assert await task3.get_output() is None
        """
        logger.debug(f"Getting output for task {self.name}")
        return await self._output.get()

    def status_label(self, status: TaskStatus) -> str:
        """Return a formatted status label for the task.

        Args:
            status (fabricatio.constants.TaskStatus): The status of the task.

        Returns:
            str: The formatted status label.
        """
        return Event.instantiate_from(self.namespace).push(self.name).push(status).collapse()

    @cached_property
    def pending_label(self) -> str:
        """Return the pending status label for the task.

        Returns:
            str: The pending status label.
        """
        return self.status_label(TaskStatus.Pending)

    @cached_property
    def running_label(self) -> str:
        """Return the running status label for the task.

        Returns:
            str: The running status label.
        """
        return self.status_label(TaskStatus.Running)

    @cached_property
    def finished_label(self) -> str:
        """Return the finished status label for the task.

        Returns:
            str: The finished status label.
        """
        return self.status_label(TaskStatus.Finished)

    @cached_property
    def failed_label(self) -> str:
        """Return the failed status label for the task.

        Returns:
            str: The failed status label.
        """
        return self.status_label(TaskStatus.Failed)

    @cached_property
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

        logger.debug(f"Emitting finished event for task {self.name}")
        await EMITTER.emit(self.finished_label, self)
        logger.debug(f"Setting output for task {self.name}")
        await self._output.put(output)
        return self

    async def start(self) -> Self:
        """Mark the task as running.

        Returns:
            Task: The running instance of the `Task` class.
        """
        logger.info(f"Starting task `{self.name}`")
        self._status = TaskStatus.Running
        await EMITTER.emit(self.running_label, self)
        return self

    async def cancel(self) -> Self:
        """Mark the task as cancelled.

        Returns:
            Task: The cancelled instance of the `Task` class.
        """
        logger.info(f"Cancelling task `{self.name}`")
        self._status = TaskStatus.Cancelled
        await self._output.put(None)
        await EMITTER.emit(self.cancelled_label, self)
        return self

    async def fail(self) -> Self:
        """Mark the task as failed.

        Returns:
            Task: The failed instance of the `Task` class.
        """
        logger.info(f"Failing task `{self.name}`")
        self._status = TaskStatus.Failed
        await self._output.put(None)
        await EMITTER.emit(self.failed_label, self)
        return self

    def publish(self, new_namespace: Optional[NameSpace] = None, *, event: Optional[NameSpace] = None) -> Self:
        """Publish the task to the event bus.

        Args:
            new_namespace(EventLike, optional): The new namespace to move the task to.
            event(EventLike, optional): The event to publish.

        Returns:
            Task: The published instance of the `Task` class.
        """
        if event is not None:
            logger.debug(f"Publishing task `{self.name}` to `{event}`.")
            EMITTER.emit_future(Event.instantiate_from(event).collapse(), self)
            return self

        if new_namespace is not None:
            self.move_to(new_namespace)
        logger.info(f"Publishing task `{self.name}` to `{(label := self.pending_label)}`.")
        EMITTER.emit_future(label, self)
        return self

    async def delegate(
        self, new_namespace: Optional[NameSpace] = None, *, event: Optional[NameSpace] = None
    ) -> T | None:
        """Delegate the task to the event.

        Args:
            new_namespace (EventLike, optional): The new namespace to move the task to.
            event (EventLike, optional): The event to publish.

        Returns:
            T|None: The output of the task.
        """
        if event is not None:
            logger.debug(f"Publishing task `{self.name}` to `{event}`.")
            EMITTER.emit_future(Event.instantiate_from(event).collapse(), self)
            return await self.get_output()

        if new_namespace is not None:
            self.move_to(new_namespace)
        logger.info(f"Delegating task `{(label := self.pending_label)}`")
        EMITTER.emit_future(label, self)
        return await self.get_output()

    def delegate_blocking(
        self, new_namespace: Optional[NameSpace] = None, *, event: Optional[NameSpace] = None
    ) -> T | None:
        """Delegate the task to the event in a blocking manner.

        Args:
            new_namespace (EventLike, optional): The new namespace to move the task to.
            event (EventLike, optional): The event to publish.

        Returns:
            T|None: The output of the task.
        """
        return run(self.delegate(new_namespace, event=event))

    @cached_property
    def briefing(self) -> str:
        """Return a briefing of the task including its goal.

        Returns:
            str: The briefing of the task.
        """
        return TEMPLATE_MANAGER.render_template(
            CONFIG.templates.task_briefing_template,
            self.model_dump(),
        )

    def is_running(self) -> bool:
        """Check if the task is running.

        Returns:
            bool: True if the task is running, False otherwise.
        """
        return self._status == TaskStatus.Running

    def is_finished(self) -> bool:
        """Check if the task is finished.

        Returns:
            bool: True if the task is finished, False otherwise.
        """
        return self._status == TaskStatus.Finished

    def is_failed(self) -> bool:
        """Check if the task is failed.

        Returns:
            bool: True if the task is failed, False otherwise.
        """
        return self._status == TaskStatus.Failed

    def is_cancelled(self) -> bool:
        """Check if the task is cancelled.

        Returns:
            bool: True if the task is cancelled, False otherwise.
        """
        return self._status == TaskStatus.Cancelled

    def is_pending(self) -> bool:
        """Check if the task is pending.

        Returns:
            bool: True if the task is pending, False otherwise.
        """
        return self._status == TaskStatus.Pending
