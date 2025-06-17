"""Module containing configuration classes for fabricatio-tool."""

from typing import Literal, NamedTuple, Set

from fabricatio_core import CONFIG
from pydantic import BaseModel, Field


class CheckConfigNamedTuple(NamedTuple):
    """Configuration for check modules, imports, and calls."""

    targets: Set[str]
    """targets: A set of strings representing the targets to check."""
    mode: Literal["whitelist", "blacklist"] = "whitelist"
    """mode: The mode to use for checking. Can be either "whitelist" or "blacklist"."""


class ToolConfig(BaseModel):
    """Configuration for fabricatio-tool."""

    check_modules: CheckConfigNamedTuple = Field(default_factory=lambda: CheckConfigNamedTuple(targets=set()))
    """Modules that are forbidden to be imported."""
    check_imports: CheckConfigNamedTuple = Field(default_factory=lambda: CheckConfigNamedTuple(targets=set()))
    """Imports that are forbidden to be used."""
    check_calls: CheckConfigNamedTuple = Field(default_factory=lambda: CheckConfigNamedTuple(targets=set()))
    """"Calls that are forbidden to be used."""


tool_config = CONFIG.load("tool", ToolConfig)
__all__ = ["tool_config"]
