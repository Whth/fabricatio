"""A module for the task capabilities of the Fabricatio library."""

from abc import ABC
from typing import Optional, Set, Unpack

from fabricatio_core import Task
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.journal import logger
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.models.role import Role
from fabricatio_core.rust import TEMPLATE_MANAGER
from more_itertools import flatten

from fabricatio_capabilities.config import capabilities_config


class ProposeTask(Propose, ABC):
    """A class that proposes a task based on a prompt."""

    async def propose_task[T](
        self,
        prompt: str,
        **kwargs: Unpack[ValidateKwargs[Task[T]]],
    ) -> Optional[Task[T]]:
        """Asynchronously proposes a task based on a given prompt and parameters.

        Parameters:
            prompt: The prompt text for proposing a task, which is a string that must be provided.
            **kwargs: The keyword arguments for the LLM (Large Language Model) usage.

        Returns:
            A Task object based on the proposal result.
        """
        if not prompt:
            logger.error(err := "Prompt must be provided.")
            raise ValueError(err)

        return await self.propose(Task, prompt, **kwargs)


class DispatchTask(UseLLM, ABC):
    """A class that dispatches a task based on a task object."""

    async def dispatch_task[T](
        self,
        task: Task[T],
        candidates: Set[Role],
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional[T]:
        """Asynchronously dispatches a task to an appropriate delegate based on candidate selection.

        This method uses a template to render instructions for selecting the most suitable candidate,
        then delegates the task to that selected candidate by resolving its namespace.

        Parameters:
            task: The task object to be dispatched. It must support delegation.
            candidates: A mapping of identifiers to WithBriefing instances representing available delegates.
                        Each key is a unique identifier and the corresponding value contains briefing details.
            **kwargs: Keyword arguments unpacked from ChooseKwargs, typically used for LLM configuration.

        Returns:
            The result of the delegated task execution, which is of generic type T.

        Raises:
            ValueError: If no valid target is picked or if delegation fails.
            KeyError: If the selected target does not exist in the reverse mapping.
        """
        inst = TEMPLATE_MANAGER.render_template(
            capabilities_config.dispatch_task_template,
            {
                "task": task.briefing,
                "candidates": [c.briefing for c in candidates],
                "possible_values": list(flatten((e.collapse() for e in r.registry) for r in candidates)),
            },
        )
        task_event = await self.ageneric_string(inst, **kwargs)
        if task_event:
            return await task.delegate(event=task_event)
        logger.error("Failed to decide where the task should be dispatched to.")
        return None
