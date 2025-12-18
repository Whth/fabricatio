"""Module containing configuration classes for fabricatio-tool."""

from typing import Dict, List, Literal, Optional, Set, TypedDict

from fabricatio_core import CONFIG
from pydantic import BaseModel, Field, JsonValue


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


class ServiceConfig(TypedDict, total=False):
    """Configuration for a single MCP service instance."""

    type: Literal["stdio", "sse", "stream", "worker"]
    """The transport protocol type (stdio, sse, stream, worker), default is stdio."""

    command: Optional[str]
    """The execution command for stdio-type services"""

    url: Optional[str]
    """The endpoint URL for SSE/stream/worker-type services"""

    args: List[str]
    """Command-line arguments for stdio services"""

    env: Dict[str, JsonValue]
    """Environment variables to set for service process"""


class ToolConfig(BaseModel):
    """Configuration for fabricatio-tool."""

    draft_tool_usage_code_template: str = "built-in/draft_tool_usage_code"
    """The name of the draft tool usage code template which will be used to draft tool usage code."""

    check_modules: CheckConfigModel = Field(default_factory=CheckConfigModel)
    """Modules that are forbidden/allowed to be imported."""
    check_imports: CheckConfigModel = Field(default_factory=lambda: CheckConfigModel(targets={"math"}))
    """Imports that are forbidden/allowed to be used."""
    check_calls: CheckConfigModel = Field(
        default_factory=lambda: CheckConfigModel(
            targets={"str", "int", "float", "bool", "dict", "set", "list", "pathlib.Path"}
        )
    )
    """Calls that are forbidden/allowed to be used."""

    mcp_servers: Dict[str, ServiceConfig] = Field(default_factory=dict)
    """MCP servers that are allowed to be used."""

    confirm_on_ops: bool = True
    """Whether to confirm operations before executing them."""

    logging_on_ops: bool = True
    """Whether to log operations before executing them."""


tool_config = CONFIG.load("tool", ToolConfig)

__all__ = ["CheckConfigModel", "ServiceConfig", "ToolConfig", "tool_config"]
