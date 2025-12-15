"""A module for defining tools and toolboxes.

This module provides classes for defining tools and toolboxes, which can be used to manage and execute callable functions
with additional functionalities such as logging, execution info, and briefing.
"""

from functools import cached_property
from inspect import iscoroutinefunction, signature
from typing import Any, Callable, List, Optional, Self, overload

from fabricatio_core.decorators import logging_execution_info
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import WithBriefing
from pydantic import Field

from fabricatio_tool.config import tool_config
from fabricatio_tool.decorators import confirm_to_execute


class Tool[**P, R](WithBriefing):
    """A class representing a tool with a callable source function.

    This class encapsulates a callable function (source) and provides methods to invoke it, log its execution, and generate
    a brief description (briefing) of the tool.
    """

    name: str = Field(default="")
    """The name of the tool."""

    description: str = Field(default="")
    """The description of the tool."""

    source: Callable[P, R]
    """The source function of the tool."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the tool with a name and a source function.

        This method sets the tool's name and description based on the source function's name and docstring.

        Args:
            __context (Any): Context passed during model initialization.

        Raises:
            RuntimeError: If the tool does not have a source function.
        """
        self.name = self.name or self.source.__name__

        if not self.name:
            raise RuntimeError("The tool must have a source function.")

        self.description = self.description or self.source.__doc__ or ""
        self.description = self.description.strip()

    def invoke(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Invoke the tool's source function with the provided arguments.

        This method logs the invocation of the tool and then calls the source function with the given arguments.

        Args:
            *args (P.args): Positional arguments to be passed to the source function.
            **kwargs (P.kwargs): Keyword arguments to be passed to the source function.

        Returns:
            R: The result of the source function.
        """
        logger.info(f"Invoking tool: {self.name}")
        return self.source(*args, **kwargs)

    @cached_property
    def signature(self) -> str:
        """Return the signature of the tool's source function."""
        return f"{'async ' if iscoroutinefunction(self.source) else ''}def {self.name}{signature(self.source)}:"

    @property
    def briefing(self) -> str:
        """Return a brief description of the tool.

        This method generates a brief description of the tool, including its name, signature, and description.

        Returns:
            str: A brief description of the tool.
        """
        lines = self.description.split("\n")
        lines_indent = [f"    {line}" for line in ['"""', *lines, '"""']]
        return f"{self.signature}\n{'\n'.join(lines_indent)}"


class ToolBox(WithBriefing):
    """A class representing a collection of tools.

    This class manages a list of tools and provides methods to add tools, retrieve tools by name, and generate a brief
    description (briefing) of the toolbox.
    """

    description: str = ""
    """The description of the toolbox."""

    tools: List[Tool] = Field(default_factory=list, frozen=True)
    """A list of tools in the toolbox."""

    @overload
    def collect_tool[**P, R](
        self, *, confirm: bool = tool_config.confirm_on_ops, logging: bool = tool_config.logging_on_ops
    ) -> Callable[[Callable[P, R]], Callable[P, R]]: ...

    @overload
    def collect_tool[**P, R](self, func: Callable[P, R]) -> Callable[P, R]: ...

    def collect_tool[**P, R](
        self,
        func: Optional[Callable[P, R]] = None,
        *,
        confirm: bool = tool_config.confirm_on_ops,
        logging: bool = tool_config.logging_on_ops,
    ) -> Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R]:
        """Add a callable function to the toolbox as a tool.

        This method wraps the function with logging execution info and adds it to the toolbox.

        Args:
            func (Callable[P, R]): The function to be added as a tool.
            confirm (bool, optional): Whether to confirm before executing the function. Defaults to True.
            logging (bool, optional): Whether to log the execution info. Defaults to True.

        Returns:
            Callable[P, R]: The added function.
        """

        def _wrapper(f: Callable[P, R]) -> Callable[P, R]:
            tool = logging_execution_info(f) if logging else f
            tool = confirm_to_execute(tool) if confirm else tool
            self.tools.append(Tool(source=tool))
            return f

        if func is None:
            return _wrapper
        return _wrapper(func)

    def add_tool[**P, R](
        self,
        func: Callable[P, R],
        *,
        confirm: bool = tool_config.confirm_on_ops,
        logging: bool = tool_config.logging_on_ops,
    ) -> Self:
        """Add a callable function to the toolbox as a tool.

        This method wraps the function with logging execution info and adds it to the toolbox.

        Args:
            func (Callable): The function to be added as a tool.
            confirm (bool, optional): Whether to confirm before executing the function. Defaults to True.
            logging (bool, optional): Whether to log the execution info. Defaults to True.

        Returns:
            Self: The current instance of the toolbox.
        """
        tool = logging_execution_info(func) if logging else func
        tool = confirm_to_execute(tool) if confirm else tool
        self.tools.append(Tool(source=tool))
        return self

    @property
    def briefing(self) -> str:
        """Return a brief description of the toolbox.

        This method generates a brief description of the toolbox, including its name, description, and a list of tools.

        Returns:
            str: A brief description of the toolbox.
        """
        list_out = "\n".join([tool.signature for tool in self.tools])
        toc = f"## {self.name}: {self.description}\n## {len(self.tools)} tools available:"
        return f"{toc}\n{list_out}"

    def get(self, name: str) -> Optional[Tool]:
        """Retrieve a tool by its name from the toolbox.

        This method looks up and returns a tool with the specified name from the list of tools in the toolbox.

        Args:
            name (str): The name of the tool to retrieve.

        Returns:
            Optional[Tool]: The tool instance with the specified name if found; otherwise, None.
        """
        return next((tool for tool in self.tools if tool.name == name), None)

    def __hash__(self) -> int:
        """Return a hash of the toolbox based on its briefing.

        Returns:
            int: A hash value based on the toolbox's briefing.
        """
        return hash(self.briefing)
