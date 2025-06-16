"""Module containing configuration classes for fabricatio-tool."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class ToolConfig:
    """Configuration for fabricatio-tool."""


tool_config = CONFIG.load("tool", ToolConfig)
__all__ = ["tool_config"]
