"""Tests for the MCP server layer: schema building, ToolBox conversion, and end-to-end transport roundtrips."""

import sys
from pathlib import Path
from typing import cast

from fabricatio_tool.mcp_server import build_input_schema
from fabricatio_tool.models.tool import ToolBox
from fabricatio_tool.rust import MCPManager, MCPServer

TESTS_DIR = Path(__file__).parent


def typed_func(x: int, y: str = "a") -> str:
    """Concatenate an int and a string.

    Longer description that is not part of the first paragraph.
    """
    return f"{x}{y}"


def untyped_func(x) -> str:  # noqa: ANN001 — untyped parameters are the tested behavior
    """Untyped parameter."""
    return str(x)


def varargs_func(*args: int, **kwargs: str) -> str:
    """Varargs function."""
    return str(args) + str(kwargs)


def raising_func(x: int) -> str:
    """Always raises."""
    raise RuntimeError("boom")


async def hello(name: str) -> str:
    """Async greeting."""
    return f"hello {name}"


def test_build_input_schema_typed() -> None:
    """Typed params become required/defaulted schema fields."""
    schema = build_input_schema(typed_func)
    props = cast("dict[str, object]", schema["properties"])
    x_props = cast("dict[str, object]", props["x"])
    y_props = cast("dict[str, object]", props["y"])
    assert x_props["type"] == "integer"
    assert "default" not in x_props
    assert y_props["type"] == "string"
    assert y_props["default"] == "a"
    assert schema["required"] == ["x"]


def test_build_input_schema_skips_varargs() -> None:
    """*args/**kwargs are excluded from the schema."""
    schema = build_input_schema(varargs_func)
    props = cast("dict[str, object]", schema["properties"])
    assert "args" not in props
    assert "kwargs" not in props


def test_build_input_schema_untyped_is_open() -> None:
    """An untyped parameter degrades to an open schema."""
    schema = build_input_schema(untyped_func)
    props = cast("dict[str, object]", schema["properties"])
    assert "x" in props


def test_toolbox_to_mcp_server_registers_tools() -> None:
    """A ToolBox converts to a server exposing every tool name."""
    box = ToolBox(name="math", description="Math tools").add_tool(typed_func)
    server = box.to_mcp_server()
    tools = server.list_tools()
    assert "typed_func" in tools
    assert server.url is None


async def test_http_e2e_call_tool_and_error() -> None:
    """A stream client lists and calls tools over streamable HTTP; raising tools surface their error text."""
    server = MCPServer.create("test-server", "0.0.0", None)
    server.add_tool("add", "Add an int to a string", build_input_schema(typed_func), typed_func)
    server.add_tool("hello", "Async greeting", build_input_schema(hello), hello)
    server.add_tool("raise_it", "Raises", build_input_schema(raising_func), raising_func)

    url = await server.serve_http("127.0.0.1", 0)
    assert url.startswith("http://127.0.0.1:")
    try:
        manager = await MCPManager.create({"srv": {"type": "stream", "url": url}})
        assert manager.has_client("srv")
        tools = await manager.list_tool_names("srv")
        assert set(tools) == {"add", "hello", "raise_it"}

        assert await manager.call_tool("srv", "add", {"x": 2, "y": "3"}) == ["23"]
        assert await manager.call_tool("srv", "hello", {"name": "world"}) == ["hello world"]
        error_text = await manager.call_tool("srv", "raise_it", {"x": 1})
        assert any("boom" in item for item in error_text)
    finally:
        await server.shutdown()


async def test_stdio_cli_smoke() -> None:
    """The CLI serves a module toolbox over stdio; a client pings and lists tools."""
    manager = await MCPManager.create(
        {
            "cli": {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-m", "fabricatio_tool.mcp_server", "--stdio", "mcp_fixture"],
                "env": {"PYTHONPATH": str(TESTS_DIR)},
            },
        },
    )
    assert manager.has_client("cli")
    assert await manager.ping("cli")
    tools = await manager.list_tool_names("cli")
    assert set(tools) == {"greet", "failing"}
    assert await manager.call_tool("cli", "greet", {"name": "mcp"}) == ["hello mcp"]
    error_text = await manager.call_tool("cli", "failing", {"x": 0})
    assert any("fixture boom" in item for item in error_text)
