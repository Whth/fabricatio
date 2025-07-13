"""This module contains the capabilities for the agent."""

from typing import Any, Unpack

from fabricatio_capabilities.capabilities.task import DispatchTask
from fabricatio_core.models.kwargs_types import GenerateKwargs
from fabricatio_core.rust import TEMPLATE_MANAGER
from fabricatio_diff.capabilities.diff_edit import DiffEdit
from fabricatio_digest.capabilities.digest import Digest
from fabricatio_judge.capabilities.advanced_judge import EvidentlyJudge, VoteJudge
from fabricatio_memory.capabilities.remember import Remember
from fabricatio_question.capabilities.questioning import Questioning
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_team.capabilities.team import Cooperate
from fabricatio_thinking.capabilities.thinking import Thinking
from fabricatio_tool.capabilities.handle import Handle

from fabricatio_agent.config import agent_config


class Fulfill(
    Remember,
    Censor,
    VoteJudge,
    EvidentlyJudge,
    DispatchTask,
    DiffEdit,
    Questioning,
    Thinking,
    Digest,
    Handle,
    Cooperate,
):
    """This class represents an agent with all capabilities enabled."""

    async def fulfill(self, request: str, check_capable: bool = True, **kwargs: Unpack[GenerateKwargs]) -> Any:
        """This method is used to fullfill a request."""
        if check_capable and await self.evidently_judge(
            TEMPLATE_MANAGER.render_template(
                agent_config.fulfill_capable_check_template, {"request": request, "tools": self.browse_toolboxes()}
            ),
            **kwargs,
        ):
            return

        await self.digest(request, self.teammates, **kwargs)
