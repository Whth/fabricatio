"""Module for the Digest class, which generates task lists based on requirements."""

from abc import ABC
from typing import Optional, Set, Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.models.role import RoleName, get_registered_role
from more_itertools.recipes import flatten

from fabricatio_digest.config import digest_config
from fabricatio_digest.models.tasklist import TaskList


class Digest(Propose, ABC):
    """A class that generates a task list based on a requirement."""

    async def digest(
        self,
        requirement: str,
        receptions: Set[RoleName],
        **kwargs: Unpack[ValidateKwargs[Optional[TaskList]]],
    ) -> Optional[TaskList]:
        """Generate a task list based on the given requirement and receptions.

        This method utilizes a template to construct instructions for creating
        a sequence of tasks that fulfill the specified requirement, considering
        the provided receptions.

        Args:
            requirement (str): A string describing the requirement to be fulfilled.
            receptions (Set[RoleName]): A set of role names indicating the roles
            **kwargs (Unpack[ValidateKwargs[Optional[TaskList]]]): Additional keyword
                                  arguments for validation and configuration.

        Returns:
            Optional[TaskList]: A TaskList object containing the generated tasks if
                                successful, or None if task generation fails.
        """
        logger.debug(f"digesting requirement with: {receptions}")
        # get the instruction to build the raw_task sequence

        roles = get_registered_role(receptions)

        instruct: str = TEMPLATE_MANAGER.render_template(
            digest_config.digest_template,
            {
                "requirement": requirement,
                "receptions": [r.briefing for r in roles],
                "accepted_events": list(flatten(r.accept_events for r in roles)),
            },
        )
        return await self.propose(TaskList, instruct, **kwargs)
