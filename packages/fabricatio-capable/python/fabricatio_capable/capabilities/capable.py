"""This module contains the capabilities for the capable."""

from abc import ABC
from typing import List, Optional, Set, Unpack, overload

from fabricatio_core.models.generic import WithBriefing
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TEMPLATE_MANAGER
from fabricatio_judge.capabilities.advanced_judge import EvidentlyJudge
from fabricatio_judge.models.judgement import JudgeMent
from fabricatio_tool.capabilities.use_tool import UseTool
from fabricatio_tool.models.tool import ToolBox

from fabricatio_capable.config import capable_config


class Capable(WithBriefing, EvidentlyJudge, UseTool, ABC):
    """A class that represents a capable entity with advanced judgment and tool usage capabilities."""

    @overload
    async def capable(
        self,
        request: str,
        toolboxes: Optional[Set[ToolBox]],
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> Optional[JudgeMent]:
        """Processes a capability request for a single string input.

        Args:
            request: A string representing the input request.
            toolboxes: An optional set of ToolBox objects to be used for processing the request.
            **kwargs: Additional keyword arguments unpacked from ValidateKwargs[JudgeMent].

        Returns:
            Optional judgment result based on the processed request.
        """

    @overload
    async def capable(
        self,
        request: List[str],
        toolboxes: Optional[Set[ToolBox]],
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> List[Optional[JudgeMent]]:
        """Processes capability requests for a list of string inputs.

        Args:
            request: A list of strings representing the input requests.
            toolboxes: An optional set of ToolBox objects to be used for processing the requests.
            **kwargs: Additional keyword arguments unpacked from ValidateKwargs[JudgeMent].

        Returns:
            A list of optional judgment results corresponding to each input request.
        """

    async def capable(
        self,
        request: str | List[str],
        toolboxes: Optional[Set[ToolBox]],
        **kwargs: Unpack[ValidateKwargs[JudgeMent]],
    ) -> None | JudgeMent | List[JudgeMent] | List[JudgeMent | None]:
        """Processes a capability request using the provided toolboxes and additional arguments.

        Args:
            request: A string or list of strings representing the input request(s).
            toolboxes: An optional set of ToolBox objects to be used for processing the request.
            **kwargs: Additional keyword arguments unpacked from ValidateKwargs[JudgeMent].

        Returns:
            The result of the capability processing, which could be None, a single judgment,
            or a list of judgments (or Nones) depending on the input and processing outcome.
        """
        toolboxes = toolboxes or self.toolboxes

        return await self.evidently_judge(
            TEMPLATE_MANAGER.render_template(
                capable_config.capable_template,
                {
                    "briefing": self.briefing,
                    "request": request,
                    "toolboxes": [t.briefing for t in toolboxes],
                }
                if isinstance(request, str)
                else [
                    {
                        "briefing": self.briefing,
                        "request": r,
                        "toolboxes": [t.briefing for t in toolboxes],
                    }
                    for r in request
                ],
            ),
            **kwargs,
        )
