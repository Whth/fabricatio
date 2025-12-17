"""Module for the CooperativeDigest class, which extends the Digest capability with cooperative functionality."""

from fabricatio_core.utils import cfg, ok

cfg(feats=["digest"])
from typing import Optional, Unpack

from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TEMPLATE_MANAGER
from fabricatio_digest.capabilities.digest import Digest
from fabricatio_digest.models.tasklist import TaskList

from fabricatio_team.capabilities.team import Cooperate


class CooperativeDigest(Cooperate, Digest):
    """A class that extends the Digest capability with cooperative functionality."""

    async def cooperative_digest(
        self,
        requirement: str,
        **kwargs: Unpack[ValidateKwargs[Optional[TaskList]]],
    ) -> Optional[TaskList]:
        """Generate a task list based on the given requirement, considering the team members."""
        return await self.digest(
            TEMPLATE_MANAGER.render_template("cooperative_digest_template", {"requirement": requirement}),
            ok(self.team_members, "Team member not specified!"),
            **kwargs,
        )
