from inspect import signature, getfullargspec
from typing import Callable, ParamSpec, TypeVar, List

from pydantic import Field

from fabricatio.models.generic import WithBriefing

P = ParamSpec("P")
R = TypeVar("R")


class Tool(WithBriefing):
    """A class representing a tool with a callable source function."""
    source: Callable[P, R]

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Invoke the tool's source function with the provided arguments."""
        return self.source(*args, **kwargs)

    def briefing(self) -> str:
        """Return a brief description of the tool.

        Returns:
            str: A brief description of the tool.
        """
        source_signature = str(signature(self.source))
        # 获取源函数的返回类型
        return_annotation = getfullargspec(self.source).annotations.get('return', 'None')
        return f"{self.name}{source_signature} -> {return_annotation}\n{self.description}"


class ToolBox(WithBriefing):
    """A class representing a collection of tools."""
    tools: List[Tool] = Field(default_factory=list)
    """A list of tools in the toolbox."""

    def collect_tool(self, func: Callable[P, R]) -> Callable[P, R]:
        """Add a callable function to the toolbox as a tool.

        Args:
            func (Callable[P, R]): The function to be added as a tool.

        Returns:
            Callable[P, R]: The added function.

        Raises:
            AssertionError: If the provided function is not callable or lacks a name.
        """
        assert callable(func), "The tool must be a callable function."
        assert func.__name__, "The tool must have a name."

        tool = Tool(source=func, name=func.__name__, description=func.__doc__ or "")
        self.tools.append(tool)
        return func

    def briefing(self) -> str:
        """Return a brief description of the toolbox.

        Returns:
            str: A brief description of the toolbox.
        """
        list_out = "\n\n".join([f'- {tool.briefing}' for tool in self.tools])
        toc = (f"## {self.name}: {self.description}\n"
               f"## {len(self.tools)} tools available:\n")
        return f"{toc}\n\n{list_out}"

    def invoke_tool(self, name: str, *args: P.args, **kwargs: P.kwargs) -> R:
        """Invoke a tool by name with the provided arguments.

        Args:
            name (str): The name of the tool to invoke.
            *args (P.args): Positional arguments to pass to the tool.
            **kwargs (P.kwargs): Keyword arguments to pass to the tool.

        Returns:
            R: The result of the tool's execution.

        Raises:
            AssertionError: If no tool with the specified name is found.
        """
        tool = next((tool for tool in self.tools if tool.name == name), None)
        assert tool, f"No tool named {name} found."
        return tool(*args, **kwargs)
