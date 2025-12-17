"""Built-in actions."""

from typing import ClassVar, Optional, Set

from fabricatio_core import Action, Task
from fabricatio_core.utils import ok
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
        br = task_input.briefing
        code_lang = self.coding_language or await self.ageneric_string(
            f"{task_input.briefing}\n\nAccording to the briefing above, what is the required coding language?"
            f"Your response shall contains only the coding language' official name, you MUST not output any other stuffs."
        )

        return await self.acode_string(br, ok(code_lang))


class MakeSpecification(Action, Agent):
    """Make a specification for a task."""

    ctx_override: ClassVar[bool] = True

    output_key: str = "specification"

    async def _execute(self, prompt: str, **cxt) -> Optional[str]:
        """Execute the action."""


class Architect(Action, Agent):
    """Architectural design and planning action.

    This action performs high-level system design and planning by:
    1. Analyzing the task briefing
    2. Creating a detailed architectural plan
    3. Generating subtasks for team members
    4. Coordinating execution of those subtasks

    The architect focuses on the overall structure and coordination
    rather than implementation details.
    """

    ctx_override: ClassVar[bool] = True

    async def _execute(self, task_input: Task, **cxt) -> bool:
        """Execute the action."""
        br = task_input.briefing
        planning = await self.thinking(f"Current directory tree:\n{treeview()}\n\n{br}")

        tk = ok(
            await self.digest(
                planning.export_branch_string() or br, ok(self.team_members, "Team member not specified!")
            )
        )
        await tk.execute()

        # TODO impl
        return True


class ReviewCode(Action, Agent):
    """Review code and suggest improvements."""

    ctx_override: ClassVar[bool] = True

    async def _execute(self, prompt: str, **cxt) -> Optional[str]:
        """Execute the action."""
        return self.save_checkpoint()
