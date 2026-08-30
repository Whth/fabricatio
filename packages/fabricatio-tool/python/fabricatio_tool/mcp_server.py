"""Expose native Python functions as an MCP (Model Context Protocol) server.

This module is the server-side counterpart of :mod:`fabricatio_tool.mcp`
(client only). It provides:

- :func:`get_global_mcp_server` — a singleton ``MCPServer`` (name
  ``"fabricatio"``) backed by the Rust ``mcp-server`` crate.
- :func:`build_input_schema` — derive a JSON input schema from a Python
  callable's signature.
- :func:`add_tool` — register a callable on the global server.
- :func:`serve` / :func:`serve_stdio` — run the server over streamable HTTP
  or stdio.
- :func:`main` — the ``python -m fabricatio_tool.mcp_server`` CLI.

Nothing is served until a transport is started; tools are registered with
:func:`add_tool` or via ``ToolBox.to_mcp_server()`` first.
"""

import argparse
import asyncio
import importlib
import inspect
import sys
from collections.abc import Callable
from importlib.metadata import version
from inspect import Parameter, signature
from typing import Any, cast, get_type_hints

from fabricatio_core.decorators import once
from fabricatio_core.journal import logger
from pydantic import create_model

from fabricatio_tool.models.tool import ToolBox
from fabricatio_tool.rust import MCPServer

__all__ = [
    "add_tool",
    "build_input_schema",
    "get_global_mcp_server",
    "main",
    "register_callable",
    "register_toolbox",
    "serve",
    "serve_stdio",
]


@once
def get_global_mcp_server() -> MCPServer:
    """Get the global MCP server instance.

    Returns:
        The singleton MCPServer named "fabricatio" versioned by the installed
        fabricatio-tool package.
    """
    return MCPServer.create("fabricatio", version("fabricatio-tool"), None)


def _first_docstring_line(func: Callable[..., object]) -> str:
    """Extract the first paragraph of a callable's docstring."""
    doc = inspect.getdoc(func) or ""
    return doc.strip().splitlines()[0].strip() if doc.strip() else ""


def build_input_schema(func: Callable[..., object]) -> dict[str, object]:
    """Build a JSON input schema from a function's signature.

    Positional-or-keyword parameters become required (or defaulted) fields
    with their type annotations resolved via ``typing.get_type_hints``.
    ``self``/``cls`` and ``*args``/``**kwargs`` are skipped; untyped
    parameters degrade to an open schema with a warning.

    Args:
        func: The callable to derive the schema from.

    Returns:
        A JSON Schema object (``{"type": "object", "properties": ...}``).
    """
    hints = get_type_hints(func)
    fields: dict[str, object] = {}
    for name, param in signature(func).parameters.items():
        if param.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
            continue
        if name in ("self", "cls"):
            continue
        if param.annotation is Parameter.empty:
            logger.warn(
                f"Parameter {name!r} of {getattr(func, '__name__', func)} has no type annotation; treating it as Any",
            )
            ann = Any
        else:
            ann = hints[name]
        if param.default is Parameter.empty:
            fields[name] = (ann, ...)
        else:
            fields[name] = (ann, param.default)
    return create_model(
        f"{getattr(func, '__name__', 'tool')}_input",
        **cast("dict[str, Any]", fields),
    ).model_json_schema()


def register_callable(
    server: MCPServer,
    func: Callable[..., object],
    *,
    name: str | None = None,
    description: str | None = None,
) -> str:
    """Register a callable on the given server.

    Args:
        server: The server to register onto.
        func: The callable to register.
        name: The tool name; defaults to ``func.__name__``.
        description: The tool description; defaults to the first docstring
            paragraph, then "".

    Returns:
        The registered tool name.
    """
    tool_name = name or getattr(func, "__name__", "")
    tool_description = description or _first_docstring_line(func)
    server.add_tool(tool_name, tool_description, build_input_schema(func), func)
    return tool_name


def register_toolbox(server: MCPServer, box: ToolBox) -> None:
    """Register every tool of a ToolBox onto the given server.

    Args:
        server: The server to register onto.
        box: The ToolBox whose tools are registered.
    """
    for tool in box.tools:
        server.add_tool(
            tool.name or getattr(tool.source, "__name__", ""),
            tool.description or _first_docstring_line(tool.source),
            build_input_schema(tool.source),
            tool.source,
        )


def add_tool(
    func: Callable[..., object],
    *,
    name: str | None = None,
    description: str | None = None,
) -> str:
    """Register a callable on the global MCP server.

    Args:
        func: The callable to register.
        name: The tool name; defaults to ``func.__name__``.
        description: The tool description; defaults to the first docstring
            paragraph, then "".

    Returns:
        The registered tool name.
    """
    return register_callable(get_global_mcp_server(), func, name=name, description=description)


async def serve(host: str = "127.0.0.1", port: int = 9847) -> str:
    """Serve the global server over streamable HTTP.

    Args:
        host: The interface to bind (default "127.0.0.1").
        port: The port to bind (default 9847); 0 picks an ephemeral port.

    Returns:
        The server URL once the listener is bound; the server keeps running.
    """
    return await get_global_mcp_server().serve_http(host, port)


async def serve_stdio() -> None:
    """Serve the global server over stdio until the stream closes."""
    await get_global_mcp_server().serve_stdio()


def _resolve_target(target: str) -> ToolBox | Callable[..., object]:
    """Import a CLI target: ``module:attr`` or ``module`` (attr ``toolbox``)."""
    if ":" in target:
        module_name, attr_name = target.split(":", 1)
    else:
        module_name, attr_name = target, "toolbox"
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def _resolve_cli_targets(
    parser: argparse.ArgumentParser,
    targets: list[str],
) -> list[tuple[ToolBox | Callable[..., object], str]]:
    """Import and validate every CLI target."""
    resolved: list[tuple[ToolBox | Callable[..., object], str]] = []
    for target in targets:
        try:
            obj = _resolve_target(target)
        except (ImportError, AttributeError) as exc:
            parser.error(f"cannot resolve target {target!r}: {exc}")
        if not isinstance(obj, ToolBox) and not callable(obj):
            parser.error(
                f"target {target!r} resolves to {type(obj).__name__}, expected a ToolBox or a callable",
            )
        resolved.append((obj, target))
    return resolved


def _register_targets(resolved: list[tuple[ToolBox | Callable[..., object], str]]) -> MCPServer:
    """Register every resolved CLI target onto one server."""
    server: MCPServer | None = None
    for obj, _ in resolved:
        if isinstance(obj, ToolBox):
            if server is None:
                server = obj.to_mcp_server()
            else:
                register_toolbox(server, obj)
        else:
            server = server or get_global_mcp_server()
            register_callable(server, obj)
    return server or get_global_mcp_server()


def main(argv: list[str] | None = None) -> None:
    """Serve Python tools as an MCP server from the command line.

    Args:
        argv: CLI arguments; defaults to ``sys.argv[1:]``.

    Raises:
        SystemExit: On bad arguments or unresolvable targets.
    """
    parser = argparse.ArgumentParser(
        prog="python -m fabricatio_tool.mcp_server",
        description="Serve Python functions or toolboxes as an MCP server.",
    )
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument(
        "--stdio",
        action="store_true",
        help="Serve over stdio (default). stdout belongs to the protocol; logs go to stderr.",
    )
    transport.add_argument(
        "--http",
        nargs=2,
        metavar=("HOST", "PORT"),
        help="Serve over streamable HTTP at HOST:PORT.",
    )
    parser.add_argument(
        "targets",
        nargs="+",
        help="'module:attr' (or 'module' meaning 'module:toolbox') exposing a ToolBox or a callable.",
    )
    args = parser.parse_args(argv)

    resolved = _resolve_cli_targets(parser, args.targets)
    server = _register_targets(resolved)

    # The pyo3 bridge captures the running asyncio loop when the coroutine is
    # created, so create it inside asyncio.run, never before it.
    async def _run() -> str | None:
        if args.http:
            host, port = args.http
            return await server.serve_http(host, int(port))
        await server.serve_stdio()
        return None

    url = asyncio.run(_run())
    if url is not None:
        print(f"MCP server listening on {url}", file=sys.stderr)


if __name__ == "__main__":
    main()
