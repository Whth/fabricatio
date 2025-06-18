"""Module containing configuration classes for fabricatio-tool."""

from typing import Literal, Set

from fabricatio_core import CONFIG
from pydantic import BaseModel, Field


class CheckConfigModel(BaseModel):
    """Configuration for check modules, imports, and calls."""

    targets: Set[str] = Field(default_factory=set)
    """targets: A set of strings representing the targets to check."""
    mode: Literal["whitelist", "blacklist"] = "whitelist"
    """mode: The mode to use for checking. Can be either "whitelist" or "blacklist"."""
    
    def is_blacklist(self) -> bool:
        """Check if the mode is blacklist."""
        return self.mode == "blacklist"
    
    def is_whitelist(self) -> bool:
        """Check if the mode is whitelist."""
        return self.mode == "whitelist"

class ToolConfig(BaseModel):
    """Configuration for fabricatio-tool."""

    check_modules: CheckConfigModel = Field(default_factory=CheckConfigModel)
    """Modules that are forbidden to be imported."""
    check_imports: CheckConfigModel = Field(default_factory=CheckConfigModel)
    """Imports that are forbidden to be used."""
    check_calls: CheckConfigModel = Field(default_factory=CheckConfigModel)
    """"Calls that are forbidden to be used."""


tool_config = CONFIG.load("tool", ToolConfig)
__all__ = ["tool_config","CheckConfigModel"]
