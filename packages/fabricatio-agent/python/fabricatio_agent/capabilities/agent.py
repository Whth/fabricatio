"""Agent capability implementation."""

from abc import ABC
from typing import Any, List, Optional, Unpack

from fabricatio_capabilities.capabilities.task import DispatchTask
from fabricatio_capable.capabilities.capable import Capable
from fabricatio_checkpoint.capabilities.checkpoint import Checkpoint
from fabricatio_core.models.kwargs_types import GenerateKwargs
from fabricatio_core.rust import TEMPLATE_MANAGER
from fabricatio_core.utils import ok
from fabricatio_diff.capabilities.diff_edit import DiffEdit
from fabricatio_judge.capabilities.advanced_judge import EvidentlyJudge
from fabricatio_memory.capabilities.remember import Remember
from fabricatio_question.capabilities.questioning import Questioning
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_team.capabilities.digest import CooperativeDigest
from fabricatio_thinking.capabilities.thinking import Thinking
from fabricatio_tool.capabilities.handle import Handle

from fabricatio_agent.config import agent_config


class Agent(
    Checkpoint,
    Capable,
    CooperativeDigest,
    Remember,
    Censor,
    EvidentlyJudge,
    DispatchTask,
    DiffEdit,
    Questioning,
    Thinking,
    Handle,
    ABC,
):
    """Main agent class that integrates multiple capabilities to fulfill requests.

    This class combines various capabilities like memory, thinking, task dispatching,
    and team cooperation to process and fulfill user requests.
    """

    async def fulfill(
        self,
        request: str,
        sequential_thinking: Optional[bool] = None,
        check_capable: bool = False,
        memory: bool = False,
        top_k: int = 100,
        boost_recent: bool = True,
        **kwargs: Unpack[GenerateKwargs],
    ) -> None | List[Any]:
        """Process and fulfill a request using various agent capabilities.

        Args:
            request (str): The request to be fulfilled.
            sequential_thinking (Optional[bool], optional): Whether to use sequential thinking.
                Defaults to None.
            check_capable (bool, optional): Whether to check agent capabilities before processing.
                Defaults to False.
            memory (bool, optional): Whether to use memory in processing. Defaults to False.
            top_k (int, optional): Number of top memories to recall. Defaults to 100.
            boost_recent (bool, optional): Whether to boost recent memories. Defaults to True.
            **kwargs (Unpack[GenerateKwargs]): Additional keyword arguments for generation.

        Returns:
            None | List[Any]: None if not capable, otherwise a list of execution results.

        Note:
            The method integrates multiple capabilities:

            - Checks capabilities if required
            - Recalls memories if enabled
            - Performs sequential thinking if enabled
            - Digests the request into tasks
            - Executes the generated task list
        """
        if (check_capable or agent_config.check_capable) and not await self.capable(request, **kwargs):  # pyright: ignore [reportCallIssue]
            return None
        mem = ""
        thought = ""
        if memory or agent_config.memory:
            mem = await self.recall(request, top_k, boost_recent, **kwargs)

        if sequential_thinking or agent_config.sequential_thinking:
            thought = (await self.thinking(request, **kwargs)).export_branch_string()

        task_list = ok(
            await self.digest(
                TEMPLATE_MANAGER.render_template(
                    agent_config.fulfill_prompt_template, {"request": request, "mem": mem, "thoughts": thought}
                ),
                ok(self.team_roster),
                **kwargs,
            )
        )
        task_list.add_before_exec_hook(lambda: self.save_checkpoint(f"{request[:50]}..."))

        return await task_list.execute()
