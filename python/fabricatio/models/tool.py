"""A module for defining tools and toolboxes."""

from inspect import iscoroutinefunction, signature
from typing import Any, Callable, Iterable, List, Self, Set, Union

from fabricatio.journal import logger
from fabricatio.models.generic import Base, WithBriefing
from pydantic import Field


class Tool[**P, R](WithBriefing):
    """A class representing a tool with a callable source function."""

    name: str = Field(default="")
    """The name of the tool."""

    description: str = Field(default="")
    """The description of the tool."""

    source: Callable[P, R]
    """The source function of the tool."""

    def model_post_init(self, __context: Any) -> None:
        """Initialize the tool with a name and a source function."""
        self.name = self.name or self.source.__name__
        assert self.name, "The tool must have a name."
        self.description = self.description or self.source.__doc__ or ""
        self.description = self.description.strip()

    def invoke(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Invoke the tool's source function with the provided arguments."""
        logger.info(f"Invoking tool: {self.name} with args: {args} and kwargs: {kwargs}")
        return self.source(*args, **kwargs)

    @property
    def briefing(self) -> str:
        """Return a brief description of the tool.

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
    """A class representing a collection of tools."""

    tools: List[Tool] = Field(default_factory=list)
    """A list of tools in the toolbox."""

    def collect_tool[**P, R](self, func: Callable[P, R]) -> Callable[P, R]:
        """Add a callable function to the toolbox as a tool.

        Args:
            func (Callable[P, R]): The function to be added as a tool.

        Returns:
            Callable[P, R]: The added function.
        """
        self.tools.append(Tool(source=func))
        return func

    def add_tool[**P, R](self, func: Callable[P, R]) -> Self:
        """Add a callable function to the toolbox as a tool.

        Args:
            func (Callable): The function to be added as a tool.

        Returns:
            Self: The current instance of the toolbox.
        """
        self.tools.append(Tool(source=func))
        return self

    @property
    def briefing(self) -> str:
        """Return a brief description of the toolbox.

        Returns:
            str: A brief description of the toolbox.
        """
        list_out = "\n\n".join([f"{tool.briefing}" for tool in self.tools])
        toc = f"## {self.name}: {self.description}\n## {len(self.tools)} tools available:"
        return f"{toc}\n\n{list_out}"

    def get[**P, R](self, name: str) -> Tool[P, R]:
        """Invoke a tool by name with the provided arguments.

        Args:
            name (str): The name of the tool to invoke.

        Returns:
            Tool: The tool instance with the specified name.

        Raises:
            AssertionError: If no tool with the specified name is found.
        """
        tool = next((tool for tool in self.tools if tool.name == name), None)
        assert tool, f"No tool named {name} found."
        return tool

    def __hash__(self) -> int:
        """Return a hash of the toolbox based on its briefing."""
        return hash(self.briefing)


class ToolBoxUsage(Base):
    """A class representing the usage of tools in a task."""

    toolboxes: Set[ToolBox] = Field(default_factory=set)
    """A set of toolboxes used by the instance."""

    @property
    def available_toolbox_names(self) -> List[str]:
        """Return a list of available toolbox names."""
        return [toolbox.name for toolbox in self.toolboxes]

    def supply_tools_from(self, others: Union["ToolBoxUsage", Iterable["ToolBoxUsage"]]) -> Self:
        """Supplies tools from other ToolUsage instances to this instance.

        Args:
            others ("ToolUsage" | Iterable["ToolUsage"]): A single ToolUsage instance or an iterable of ToolUsage instances
                from which to take tools.

        Returns:
            Self: The current ToolUsage instance with updated tools.
        """
        if isinstance(others, ToolBoxUsage):
            others = [others]
        for other in others:
            self.toolboxes.update(other.toolboxes)
        return self

    def provide_tools_to(self, others: Union["ToolBoxUsage", Iterable["ToolBoxUsage"]]) -> Self:
        """Provides tools from this instance to other ToolUsage instances.

        Args:
            others ("ToolUsage" | Iterable["ToolUsage"]): A single ToolUsage instance or an iterable of ToolUsage instances
                to which to provide tools.

        Returns:
            Self: The current ToolUsage instance.
        """
        if isinstance(others, ToolBoxUsage):
            others = [others]
        for other in others:
            other.toolboxes.update(self.toolboxes)
        return self
