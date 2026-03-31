"""Module containing configuration classes for fabricatio-workspace."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class WorkspaceConfig:
    """Configuration for fabricatio-workspace."""


workspace_config = CONFIG.load("workspace", WorkspaceConfig)

__all__ = ["workspace_config"]
