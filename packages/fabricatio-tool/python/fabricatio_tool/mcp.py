"""MCP (Model Context Protocol) management utilities."""

from typing import Dict

from fabricatio_core.decorators import once

from fabricatio_tool.config import ServiceConfig, tool_config
from fabricatio_tool.rust import MCPManager


@once
async def get_global_mcp_manager(conf: Dict[str, ServiceConfig] = tool_config.mcp_servers) -> MCPManager:
    """Get the global MCP manager instance."""
    return await MCPManager.create(conf)
