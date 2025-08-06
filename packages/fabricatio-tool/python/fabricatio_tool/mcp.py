"""MCP (Model Context Protocol) management utilities."""

from functools import wraps
from typing import Any, Callable, Coroutine, Dict, List

from fabricatio_tool.rust import MCPManager

from fabricatio_core.decorators import once
from fabricatio_tool.config import ServiceConfig, tool_config


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
        n = t.name
        exec(t.function_string, locals())  # noqa: S102
        f: Callable[..., List[str]] = locals().get(n)  # pyright: ignore [reportAssignmentType]

        @wraps(f)
        async def _inner(**kwargs) -> List[str]:
            return await man.call_tool(client_id, tool_name, kwargs)

        return _inner

    raise ValueError(f"Tool {tool_name} not found")
