"""Rust bindings for the Rust API of fabricatio-tool."""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set

from pydantic import JsonValue

def treeview(directory: Optional[str | Path] = None, max_depth: int = 10) -> str:
    """Return a tree view of the given directory.

    The directory is traversed recursively up to a specified depth.
    """

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
    """Metadata container for a tool's properties and specifications.

    Provides structured access to tool name, description, input schema,
    annotations, and full serialization capabilities.
    """
    @property
    def name(self) -> str:
        """Get the tool's display name as a string identifier."""
    @property
    def description(self) -> str:
        """Get the tool's human-readable description. May be empty if unspecified."""

    @property
    def input_schema(self) -> Dict[str, JsonValue]:
        """JSON schema defining expected input parameters for the tool.

        This schema follows the JSON Schema specification and validates
        the input data passed to the tool.
        """
    @property
    def annotations(self) -> Dict[str, JsonValue]:
        """Additional metadata properties in key-value format.

        Contains implementation-specific details and custom attributes
        associated with the tool.
        """

    def dump_dict(self) -> Dict[str, JsonValue]:
        """Serialize the complete tool metadata to a JSON-compatible dictionary.

        Returns:
            Dictionary representation containing all tool metadata fields.
        """
    @property
    def input_schema_string(self) -> str:
        """JSON schema string representation of the tool's input requirements.

        Serialized version of input_schema property. Provides the schema in
        a string format suitable for JSON parsing or transmission.
        """
    @property
    def annotations_string(self) -> str:
        """Stringified JSON representation of the tool's annotations metadata.

        Serialized version of annotations property. Offers machine-readable
        access to implementation-specific details in string format.
        """

    @property
    def function_header(self) -> str:
        """Python function signature string for this tool.

        Returns:
            Formatted async function signature with input parameters and return type.
        """

    @property
    def function_docstring(self) -> str:
        """Python docstring template for this tool's generated function.

        Returns:
            Pre-formatted docstring with argument descriptions and return documentation.
        """
    @property
    def function_string(self) -> str:
        """Complete Python function template for this tool's implementation.

        Returns:
            String containing full async function definition with formatted
            signature, docstring, and return type annotation.
        """

class MCPManager:
    """Manager for interacting with MCP (Model Coordination Protocol) services."""

    @staticmethod
    async def create(server_configs: Dict[str, Any]) -> MCPManager:
        """Initialize the MCP manager with server configurations.

        Args:
            server_configs: A dictionary mapping server names to their configuration objects.
        """

    async def list_tools(self, client_id: str) -> List[ToolMetaData]:
        """Asynchronously list available tools for a given client.

        Args:
            client_id: The identifier of the client requesting the tool list.

        Returns:
            A list of ToolMetaData instances representing available tools.
        """

    async def get_tool(self, client_id: str, tool_name: str) -> Optional[ToolMetaData]:
        """Retrieves metadata for a specific tool from a client.

        Args:
            client_id: The ID of the client to retrieve the tool from
            tool_name: The name of the tool to retrieve

        Returns:
            The requested tool's metadata if found
        """

    async def call_tool(self, client_id: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> List[str]:
        """Asynchronously call a specific tool with optional arguments.

        Args:
            client_id: Identifier of the calling client.
            tool_name: Name of the tool to invoke.
            arguments: Optional dictionary of arguments to pass to the tool.

        Returns:
            A list of text results returned by the tool.
        """

    def server_list(self) -> List[str]:
        """List all available servers.

        Returns:
            A list of server names.
        """

    def server_count(self) -> int:
        """Get the number of available servers.

        Returns:
            The count of servers.
        """

    async def list_tool_names(self, client_id: str) -> List[str]:
        """Retrieves a list of tool names from a client.

        Args:
            client_id: The ID of the client to retrieve tools from.

        Returns:
            A list of tool names or an error if the operation fails.
        """

    async def description_mapping(self, client_id: str) -> Dict[str, str]:
        """Retrieves a mapping of tool names to their descriptions from a client.

        Args:
            client_id: The ID of the client to retrieve tools from.

        Returns:
            A mapping of tool names to descriptions or an error if the operation fails.
        """

    async def ping(self, client_id: str) -> bool:
        """Ping a server.

        Args:
            client_id: The client ID to ping.

        Returns:
            True if the server is reachable, False otherwise.
        """

    def has_client(self, client_id: str) -> bool:
        """Check if a client exists in the manager.

        Args:
            client_id: The ID of the client to check.

        Returns:
            True if the client exists, False otherwise.
        """

    async def has_tool(self, client_id: str, tool_name: str) -> bool:
        """Check if a tool exists for a specific client.

        Args:
            client_id: The ID of the client.
            tool_name: The name of the tool.

        Returns:
            True if the tool exists, False otherwise.
        """
