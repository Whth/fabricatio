"""Module containing configuration classes for fabricatio-tool."""

from typing import Set

from fabricatio_core import CONFIG
from pydantic import BaseModel, Field


class ToolConfig(BaseModel):
    """Configuration for fabricatio-tool."""

    forbidden_modules: Set[str] = Field(default_factory=lambda: {"os", "sys", "subprocess"})
    """Modules that are forbidden to be imported."""
    forbidden_imports: Set[str] = Field(default_factory=lambda: {"os", "sys", "subprocess"})
    """Imports that are forbidden to be used."""
    forbidden_calls: Set[str] = Field(default_factory=lambda: {"exec", "breakpoint", "compile", "exit"})
    """"Calls that are forbidden to be used."""


tool_config = CONFIG.load("tool", ToolConfig)
__all__ = ["tool_config"]
