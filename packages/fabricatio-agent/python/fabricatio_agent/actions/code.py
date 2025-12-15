"""Built-in actions."""

from typing import ClassVar, Optional, Set

from fabricatio_core import Action
from fabricatio_core.utils import ok
from fabricatio_tool.models.tool import ToolBox
from fabricatio_tool.toolboxes import fs_toolbox
from pydantic import Field

from fabricatio_agent.capabilities.agent import Agent


class WriteCode(Action, Agent):
    """Write code. output the code as a string"""

    ctx_override: ClassVar[bool] = True

    toolboxes: Set[ToolBox] = Field(default={fs_toolbox})
    
    output_key:str = "code"
    
    coding_language: Optional[str]=None 
    """The coding language to use, will automatically be inferred from the prompt if not specified."""    
    async def _execute(self, prompt: str, **cxt) -> Optional[str]:
        
        code_lang =self.coding_language or await self.ageneric_string(f'{prompt}\n\nAccording to the prompt above, what is the required code language?')
        
        return await self.acode_string(prompt, ok(code_lang))


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
