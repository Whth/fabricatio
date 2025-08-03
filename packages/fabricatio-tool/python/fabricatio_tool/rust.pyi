"""Rust bindings for the Rust API of fabricatio-tool."""

from typing import Any, Dict, List, Literal, Optional, Set

class CheckConfig:
    def __init__(self, targets: Set[str], mode: Literal["whitelist", "blacklist"]) -> None:
        """Initialize a CheckConfig instance with specified targets and mode.

        Args:
            targets (Set[str]): A set of target items to be checked.
            mode (str): The checking mode, either 'whitelist' or 'blacklist'.

        Raises:
            RuntimeError: If the provided mode is neither 'whitelist' nor 'blacklist'.
        """

def gather_violations(
    source: str,
    modules: Optional[CheckConfig] = None,
    imports: Optional[CheckConfig] = None,
    calls: Optional[CheckConfig] = None,
) -> List[str]:
    """Gather violations from the given Python source code based on check configurations.

    Args:
        source (str): The Python source code to analyze.
        modules (Optional[CheckConfig]): Configuration for module checks.
        imports (Optional[CheckConfig]): Configuration for import checks.
        calls (Optional[CheckConfig]): Configuration for function call checks.

    Returns:
        List[str]: A list of violation messages found in the source code.
    """

class ToolMetaData:
    """Metadata wrapper for a tool, containing its specification and metadata."""

    def dump_dict(self) -> Dict[str, Any]:
        """Serialize the internal tool data into a Python dictionary.

        Returns:
            A dictionary representation of the tool metadata.
        """

class McpManager:
    """Manager for interacting with MCP (Model Coordination Protocol) services."""

    def __init__(self, server_configs: Dict[str, Any]) -> None:
        """Initialize the MCP manager with server configurations.

        Args:
            server_configs: A dictionary mapping server names to their configuration objects.
        """

    def list_tools(self, client_id: str) -> List[ToolMetaData]:
        """Asynchronously list available tools for a given client.

        Args:
            client_id: The identifier of the client requesting the tool list.

        Returns:
            A list of ToolMetaData instances representing available tools.
        """

    def call_tool(self, client_id: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> List[str]:
        """Asynchronously call a specific tool with optional arguments.

        Args:
            client_id: Identifier of the calling client.
            tool_name: Name of the tool to invoke.
            arguments: Optional dictionary of arguments to pass to the tool.

        Returns:
            A list of text results returned by the tool.
        """
