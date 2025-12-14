"""Built-in actions."""

from typing import ClassVar, Optional, Set

from fabricatio_core import Action
from fabricatio_tool.models.tool import ToolBox
from fabricatio_tool.toolboxes import fs_toolbox
from pydantic import Field

from fabricatio_agent.capabilities.agent import Agent


class WriteCode(Action, Agent):
    """Write code."""

    ctx_override: ClassVar[bool] = True

    enable_seq_thinking: bool = False

    toolboxes: Set[ToolBox] = Field(default={fs_toolbox})

    async def _execute(self, prompt: str, **cxt) -> Optional[str]:
        head = self.save_checkpoint()

        await self.handle(prompt)

        return head


class MakeSpecification(Action, Agent):
    """Make a specification for a task."""

    ctx_override: ClassVar[bool] = True

    output_key: str = "specification"

    async def _execute(self, prompt: str, **cxt) -> Optional[str]:
        """Execute the action."""


class Planning(Action, Agent):
    """Plan the task."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, prompt: str, **cxt) -> Optional[str]:
        """Execute the action."""


class ReviewCode(Action, Agent):
    """Review code and suggest improvements."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, prompt: str, **cxt) -> Optional[str]:
        """Execute the action."""
        return self.save_checkpoint()
