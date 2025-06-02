"""Module for the Digest class, which generates task lists based on requirements."""

from abc import ABC
from typing import List, Optional, Unpack

from fabricatio_core import TEMPLATE_MANAGER, Role
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs

from fabricatio_digest.config import digest_config
from fabricatio_digest.models.tasklist import TaskList


class Digest(Propose, ABC):
    """A class that generates a task list based on a requirement."""

    async def digest[T: Role](
        self,
        requirement: str,
        receptions: List[T],
        **kwargs: Unpack[ValidateKwargs[Optional[TaskList]]],
    ) -> Optional[TaskList]:
        """Generate a task list based on the given requirement and receptions.

        This method utilizes a template to construct instructions for creating
        a sequence of tasks that fulfill the specified requirement, considering
        the provided receptions.

        Args:
            requirement (str): A string describing the requirement to be fulfilled.
            receptions (List[T]): A list of Role objects representing the receptions
                                  to be considered in generating the task list.
            **kwargs (Unpack[ValidateKwargs[Optional[TaskList]]]): Additional keyword
                                  arguments for validation and configuration.

        Returns:
            Optional[TaskList]: A TaskList object containing the generated tasks if
                                successful, or None if task generation fails.
        """
        # get the instruction to build the raw_task sequence
        instruct = TEMPLATE_MANAGER.render_template(
            digest_config.digest_template, {"requirement": requirement, "receptions": [r.briefing for r in receptions]}
        )

        return await self.propose(TaskList, instruct, **kwargs)
