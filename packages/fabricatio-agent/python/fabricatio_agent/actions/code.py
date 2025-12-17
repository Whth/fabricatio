"""Built-in actions."""

from typing import ClassVar, Optional, Set

from fabricatio_core import Action, Task, logger
from fabricatio_core.utils import ok
from fabricatio_tool.capabilities.handle_task import HandleTask
from fabricatio_tool.models.tool import ToolBox
from fabricatio_tool.rust import treeview
from fabricatio_tool.toolboxes import fs_toolbox
from pydantic import Field

from fabricatio_agent.capabilities.agent import Agent


class WriteCode(Action, Agent):
    """Write code. output the code as a string."""

    ctx_override: ClassVar[bool] = True

    toolboxes: Set[ToolBox] = Field(default={fs_toolbox})

    output_key: str = "code"

    coding_language: Optional[str] = None
    """The coding language to use, will automatically be inferred from the prompt if not specified."""

    async def _execute(self, task_input: Task, **cxt) -> Optional[str]:
        c = ok(
            await self.acode_snippet(
                f"current directory tree:\n{treeview()}\n\n{task_input.dependencies_prompt}\n\n{task_input.briefing}",
                code_language=self.coding_language,
            )
        )
        logger.info(f"Writing code to {c.write_to}")
        c.write()
        return c.source


class CleanUp(Action, Agent, HandleTask):
    """Clean up the workspace."""

    toolboxes: Set[ToolBox] = Field(default={fs_toolbox})

    async def _execute(self, task_input: Task, **cxt) -> None:
        """Execute the action."""
        await self.handle_task(task_input, {})


class MakeSpecification(Action, Agent):
    """Make a specification for a task."""

    ctx_override: ClassVar[bool] = True

    output_key: str = "specification"

    async def _execute(self, prompt: str, **cxt) -> Optional[str]:
        """Execute the action."""


class Planning(Action, Agent):
    """Architectural design and planning action."""

    ctx_override: ClassVar[bool] = True

    sequential_thinking: bool = False
    """Whether to use sequential thinking."""

    async def _execute(self, task_input: Task, **cxt) -> bool:
        """Execute the action."""
        br = task_input.briefing
        req = f"Current directory tree:\n{treeview()}\n\n{task_input.dependencies_prompt}\n{br}"
        if self.sequential_thinking:
            planning = await self.thinking(req)
            req += f"\n\n{planning.export_branch_string()}"

        tk = ok(await self.digest(req, ok(self.team_members, "Team member not specified!")))
        await (
            tk.inject_context(sequential_thinking=self.sequential_thinking)
            .inject_description(f"This task is a sub task of {task_input.name}.\n{br}")
            .execute()
        )
        return True


class ReviewCode(Action, Agent):
    """Review code and suggest improvements."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, prompt: str, **cxt) -> Optional[str]:
        """Execute the action."""
        return self.save_checkpoint()
