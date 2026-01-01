"""Module for the CooperativeDigest class, which extends the Digest capability with cooperative functionality."""

from fabricatio_core.utils import cfg, ok

cfg(feats=["digest"])
from typing import Optional, Unpack

from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_digest.capabilities.digest import Digest
from fabricatio_digest.models.tasklist import TaskList

from fabricatio_team.capabilities.team import Cooperate


class CooperativeDigest(Cooperate, Digest):
    """A class that extends the Digest capability with cooperative functionality."""

    async def cooperative_digest(
        self,
        requirement: str,
        with_self: bool = True,
        **kwargs: Unpack[ValidateKwargs[Optional[TaskList]]],
    ) -> Optional[TaskList]:
        """Generate a task list based on the given requirement, considering the team members."""
        return await self.digest(
            requirement,
            ok(self.team_roster if with_self else self.other_member_roster, "Team member not specified!"),
            **kwargs,
        )
