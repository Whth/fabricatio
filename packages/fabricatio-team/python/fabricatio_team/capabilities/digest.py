"""Module for the CooperativeDigest class, which extends the Digest capability with cooperative functionality."""

from fabricatio_core.utils import cfg, ok

cfg(feats=["digest"])
from typing import Optional, Unpack

from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TASK
from fabricatio_digest.capabilities.digest import Digest
from fabricatio_digest.models.tasklist import TaskList

from fabricatio_team.capabilities.team import Cooperate


class CooperativeDigest(Cooperate, Digest):
    """A class that extends the Digest capability with cooperative functionality."""

    async def cooperative_digest(
        self,
        requirement: str,
        with_self: bool = True,
        *,
        send_to: str | None = TASK,
        **kwargs: Unpack[ValidateKwargs[Optional[TaskList]]],
    ) -> Optional[TaskList]:
        """Generate a task list based on the given requirement, considering the team members.

        Args:
            requirement: The requirement description for task generation.
            with_self: Whether to include self in the team roster.
            send_to: Routing group for LLM calls (TASK, SMOL, TINY, SLOW, PLAN).
            **kwargs: Additional keyword arguments forwarded to the digest method.

        Returns:
            An optional task list generated from the requirement.
        """
        return await self.digest(
            requirement,
            ok(self.team_roster if with_self else self.other_member_roster, "Team member not specified!"),
            send_to=send_to,
            **kwargs,
        )
