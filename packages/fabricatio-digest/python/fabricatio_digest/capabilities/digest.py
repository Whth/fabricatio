"""Module for the Digest class, which generates task lists based on requirements."""
from abc import ABC
from typing import List, Optional, Unpack

from fabricatio_core import TEMPLATE_MANAGER, Role, CONFIG
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_digest.models.tasklist import TaskList


class Digest(Propose, ABC):
    """A class that generates a task list based on a requirement."""

    async def digest[T:Role](self, requirement: str, receptions: List[T],
                             **kwargs: Unpack[ValidateKwargs[Optional[TaskList]]],
                             ) -> Optional[TaskList]:
        # get the instruction to build the raw_task sequence
        instruct = TEMPLATE_MANAGER.render_template(
            CONFIG.templates.digest_template,

            {"requirement": requirement,
             "receptions": [r.briefing for r in receptions]
             }

        )

        return await self.propose(TaskList, instruct, **kwargs)
