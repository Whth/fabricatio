"""MCP (Model Context Protocol) management utilities."""

from typing import Any, Callable, Coroutine, Dict, List

from fabricatio_core import logger
from fabricatio_core.decorators import once

from fabricatio_tool.config import ServiceConfig, tool_config
from fabricatio_tool.models.tool import ToolBox
from fabricatio_tool.rust import MCPManager


@once
async def get_global_mcp_manager(conf: Dict[str, ServiceConfig] = tool_config.mcp_servers) -> MCPManager:
    """Get the global MCP manager instance."""
    return await MCPManager.create(conf)


async def mcp_tool_to_function(client_id: str, tool_name: str) -> Callable[..., Coroutine[Any, Any, List[str]]]:
    """Converts a registered MCP tool into a callable async function.

    This function dynamically generates and returns an async function that wraps
    the specified tool's execution. The generated function will have:
    - A signature derived from the tool's input schema
    - A docstring containing the tool description and parameter documentation
    - Execution that delegates to the MCP manager's call_tool method

    Args:
        client_id: Identifier for the client/service hosting the tool
        tool_name: Name of the tool to convert to a function

    Returns:
        Coroutine-enabled function that accepts keyword arguments matching the tool's
        input schema and returns a list of execution result strings

    Raises:
        ValueError: If the specified tool cannot be found

    Notes:
        The generated function uses functools.wraps to preserve metadata and will
        raise if called with invalid arguments based on the tool's schema
    """
    man = await get_global_mcp_manager()

    if (t := await man.get_tool(client_id, tool_name)) is not None:
        code = f"{t.function_string}\n    return await man.call_tool(client_id, tool_name, kwargs)"
        logger.debug(f"Generating function for tool {t.name} in {client_id}")
        d = locals()
        exec(code, d)  # noqa: S102
        f: Callable[..., Coroutine[Any, Any, List[str]]] = d.get(t.name)  # pyright: ignore [reportAssignmentType]
        return f
    raise ValueError(f"Tool {tool_name} not found")


async def mcp_to_toolbox(client_id: str) -> ToolBox:
    """Converts all tools from a specified MCP client into a ToolBox.

    This function retrieves all available tools from the given MCP client,
    converts each tool into a callable async function, and adds them to
    a ToolBox instance.

    Args:
        client_id: Identifier for the client/service hosting the tools

    Returns:
        ToolBox: A toolbox containing all tools from the specified client

    Raises:
        ValueError: If the specified client cannot be found
    """
    man = await get_global_mcp_manager()

    if not man.has_client(client_id):
        raise ValueError(f"Client {client_id} not found")

    toolbox = ToolBox(name=client_id)

    for tool in await man.list_tool_names(client_id):
        func = await mcp_tool_to_function(client_id, tool)
        toolbox.add_tool(func)

    return toolbox
