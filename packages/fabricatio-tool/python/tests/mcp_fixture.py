"""Fixture module for the MCP stdio CLI smoke test.

Exposes a module-level ``toolbox`` so the CLI can be invoked as
``python -m fabricatio_tool.mcp_server --stdio mcp_fixture`` with this
directory on ``PYTHONPATH``.
"""

from fabricatio_tool.models.tool import ToolBox


def greet(name: str) -> str:
    """Greet someone by name."""
    return f"hello {name}"


def failing(x: int) -> str:
    """Always fails."""
    raise RuntimeError("fixture boom")


toolbox = ToolBox(name="fixture", description="Fixture toolbox").add_tool(greet).add_tool(failing)
