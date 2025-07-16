"""This module contains the capabilities for the agent."""

from typing import Any, List, Unpack

from fabricatio_capabilities.capabilities.task import DispatchTask
from fabricatio_capable.capabilities.capable import Capable
from fabricatio_core.models.kwargs_types import GenerateKwargs
from fabricatio_core.utils import ok
from fabricatio_diff.capabilities.diff_edit import DiffEdit
from fabricatio_digest.capabilities.digest import Digest
from fabricatio_judge.capabilities.advanced_judge import EvidentlyJudge, VoteJudge
from fabricatio_memory.capabilities.remember import Remember
from fabricatio_question.capabilities.questioning import Questioning
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_team.capabilities.team import Cooperate
from fabricatio_thinking.capabilities.thinking import Thinking
from fabricatio_tool.capabilities.handle import Handle


class Fulfill(
    Capable,
    Digest,
    Cooperate,
):
    """This class represents an agent with all capabilities enabled."""

    async def fulfill(
        self, request: str, check_capable: bool = True, **kwargs: Unpack[GenerateKwargs]
    ) -> None | List[Any]:
        """This method is used to fulfill a request."""
        if check_capable and not await self.capable(request, **kwargs):  # pyright: ignore [reportCallIssue]
            return None

        task_list = ok(await self.digest(request, self.team_members, **kwargs))

        return await task_list.execute()


class Agent(
    Fulfill,
    Remember,
    Censor,
    VoteJudge,
    EvidentlyJudge,
    DispatchTask,
    DiffEdit,
    Questioning,
    Thinking,
    Handle,
):
    """This class represents an agent with all capabilities enabled."""

    # TODO
