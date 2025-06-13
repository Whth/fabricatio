"""A module for defining tools and toolboxes.

This module provides classes for defining tools and toolboxes, which can be used to manage and execute callable functions
with additional functionalities such as logging, execution info, and briefing.
"""

from inspect import iscoroutinefunction, signature
from typing import Any, Callable, Dict, List, Optional, Self

from pydantic import Field

from fabricatio_core.decorators import logging_execution_info
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import Base, WithBriefing


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

    @property
    def briefing(self) -> str:
        """Return a brief description of the tool.

        This method generates a brief description of the tool, including its name, signature, and description.

        Returns:
            str: A brief description of the tool.
        """
        # 获取源函数的返回类型

        return f"{'async ' if iscoroutinefunction(self.source) else ''}def {self.name}{signature(self.source)}\n{_desc_wrapper(self.description)}"


def _desc_wrapper(desc: str) -> str:
    lines = desc.split("\n")
    lines_indent = [f"    {line}" for line in ['"""', *lines, '"""']]
    return "\n".join(lines_indent)


class ToolBox(WithBriefing):
    """A class representing a collection of tools.

    This class manages a list of tools and provides methods to add tools, retrieve tools by name, and generate a brief
    description (briefing) of the toolbox.
    """

    description: str = ""
    """The description of the toolbox."""

    tools: List[Tool] = Field(default_factory=list, frozen=True)
    """A list of tools in the toolbox."""

    def collect_tool[**P, R](self, func: Callable[P, R]) -> Callable[P, R]:
        """Add a callable function to the toolbox as a tool.

        This method wraps the function with logging execution info and adds it to the toolbox.

        Args:
            func (Callable[P, R]): The function to be added as a tool.

        Returns:
            Callable[P, R]: The added function.
        """
        self.tools.append(Tool(source=func))
        return func

    def add_tool[**P, R](self, func: Callable[P, R]) -> Self:
        """Add a callable function to the toolbox as a tool.

        This method wraps the function with logging execution info and adds it to the toolbox.

        Args:
            func (Callable): The function to be added as a tool.

        Returns:
            Self: The current instance of the toolbox.
        """
        self.collect_tool(logging_execution_info(func))
        return self

    @property
    def briefing(self) -> str:
        """Return a brief description of the toolbox.

        This method generates a brief description of the toolbox, including its name, description, and a list of tools.

        Returns:
            str: A brief description of the toolbox.
        """
        list_out = "\n\n".join([f"{tool.briefing}" for tool in self.tools])
        toc = f"## {self.name}: {self.description}\n## {len(self.tools)} tools available:"
        return f"{toc}\n\n{list_out}"

    def get[**P, R](self, name: str) -> Tool[P, R]:
        """Invoke a tool by name with the provided arguments.

        This method retrieves a tool by its name from the toolbox.

        Args:
            name (str): The name of the tool to invoke.

        Returns:
            Tool: The tool instance with the specified name.

        Raises:
            ValueError: If no tool with the specified name is found.
        """
        tool = next((tool for tool in self.tools if tool.name == name), None)
        if tool is None:
            err = f"No tool with the name {name} found in the toolbox."
            logger.error(err)
            raise ValueError(err)

        return tool

    def __hash__(self) -> int:
        """Return a hash of the toolbox based on its briefing.

        Returns:
            int: A hash value based on the toolbox's briefing.
        """
        return hash(self.briefing)


class ToolExecutor(Base):
    """A class representing a tool executor with a sequence of tools to execute.

    This class manages a sequence of tools and provides methods to inject tools and data into a module, execute the tools,
    and retrieve specific outputs.
    """

    candidates: List[Tool] = Field(default_factory=list, frozen=True)
    """The sequence of tools to execute."""

    data: Dict[str, Any] = Field(default_factory=dict)
    """The data that could be used when invoking the tools."""

    def inject_tools[C: Dict[str, Any]](self, cxt: Optional[C] = None) -> C:
        """Inject the tools into the provided module or default.

        This method injects the tools into the provided module or creates a new module if none is provided.

        Args:
            cxt (Optional[M]): The module to inject tools into. If None, a new module is created.

        Returns:
            M: The module with injected tools.
        """
        cxt = cxt or {}
        for tool in self.candidates:
            logger.debug(f"Injecting tool: {tool.name}")
            cxt[tool.name] = tool.invoke
        return cxt

    def inject_data[C: Dict[str, Any]](self, cxt: Optional[C] = None) -> C:
        """Inject the data into the provided module or default.

        This method injects the data into the provided module or creates a new module if none is provided.

        Args:
            cxt (Optional[M]): The module to inject data into. If None, a new module is created.

        Returns:
            M: The module with injected data.
        """
        cxt = cxt or {}
        for key, value in self.data.items():
            logger.debug(f"Injecting data: {key}")
            cxt[key] = value
        return cxt

    async def execute[C: Dict[str, Any]](self, body: str, cxt: Optional[C] = None) -> Any:
        """Execute the sequence of tools with the provided context.

        This method executes the tools in the sequence with the provided context.

        Args:
            body (str): The source code to execute.
            cxt (Optional[C]): The context to execute the tools with. If None, an empty dictionary is used.

        Returns:
            C: The context after executing the tools.
        """
        cxt = self.inject_tools(cxt)
        cxt = self.inject_data(cxt)

        fn_name = "executer"
        fn_source = f"async def {fn_name}():\n{self._indent(body)}"
        exec(fn_source, cxt)
        compiled_fn = cxt[fn_name]
        return await compiled_fn()

    @staticmethod
    def _indent(lines: str) -> str:
        """Add four spaces to each line."""
        return "\n".join([f"    {line}" for line in lines.split("\n")])

    @classmethod
    def from_recipe(cls, recipe: List[str], toolboxes: List[ToolBox]) -> Self:
        """Create a tool executor from a recipe and a list of toolboxes.

        This method creates a tool executor by retrieving tools from the provided toolboxes based on the recipe.

        Args:
            recipe (List[str]): The recipe specifying the names of the tools to be added.
            toolboxes (List[ToolBox]): The list of toolboxes to retrieve tools from.

        Returns:
            Self: A new instance of the tool executor with the specified tools.
        """
        tools = []
        while tool_name := recipe.pop(0):
            for toolbox in toolboxes:
                tools.append(toolbox.get(tool_name))

        return cls(candidates=tools)
