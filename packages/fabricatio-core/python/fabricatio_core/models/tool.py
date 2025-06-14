"""A module for defining tools and toolboxes.

This module provides classes for defining tools and toolboxes, which can be used to manage and execute callable functions
with additional functionalities such as logging, execution info, and briefing.
"""

from dataclasses import dataclass, field
from inspect import iscoroutinefunction, signature
from typing import Any, Callable, ClassVar, Dict, List, Optional, Self, Type, overload

from pydantic import Field

from fabricatio_core.decorators import logging_execution_info
from fabricatio_core.journal import logger
from fabricatio_core.models.generic import WithBriefing


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


@dataclass
class ResultCollector:
    """Used for collecting results from tools etc.

    use .submit(to: str, result: Any) to submit a result to the container with the specified key.
    use .revoke(target: str) to remove a result from the container by its source key.
    """

    container: Dict[str, Any] = field(default_factory=dict)
    """A dictionary to store results."""

    def submit(self, to: str, result: Any) -> Self:
        """Submit a result to the container with the specified key.

        Args:
            to (str): The key to store the result under.
            result (Any): The result to store in the container.

        Returns:
            Self: The current instance for method chaining.
        """
        self.container[to] = result
        return self

    def revoke(self, target: str) -> Self:
        """Remove a result from the container by its source key.

        Args:
            target (str): The key of the result to remove.

        Returns:
            Self: The current instance for method chaining.

        Raises:
            KeyError: If the key is not found in the container.
        """
        if target not in self.container:
            logger.warning(f"Key '{target}' not found in container.")
        self.container.pop(target)
        return self

    @overload
    def take[T](self, key: str, desired: Optional[Type[T]] = None) -> T | None: ...

    @overload
    def take[T](self, key: List[str], desired: Optional[Type[T]] = None) -> List[T | None]: ...

    def take[T](self, key: str | List[str], desired: Optional[Type[T]] = None) -> T | None | List[T | None]:
        """Retrieve value(s) from the container by key(s) with optional type checking.

        This method retrieves a single value or multiple values from the container based on the provided key(s).
        It supports optional type checking to ensure the retrieved value matches the expected type.

        Args:
            key (str | List[str]): A single key as a string or a list of keys to retrieve values for.
            desired (Optional[Type[T]]): The expected type of the retrieved value(s). If provided,
                type checking will be performed and None will be returned for mismatched types.

        Returns:
            T | None | List[T | None]: If key is a string, returns the value of type T or None.
                If key is a list, returns a list of values of type T or None for each key.
        """
        if isinstance(key, str):
            result = self.container.get(key)
            if desired is not None and result is not None and not isinstance(result, desired):
                logger.error(f"Type mismatch: expected {desired.__name__}, got {type(result).__name__}")
                return None
            return result
        results = []
        for k in key:
            result = self.container.get(k)
            if desired is not None and result is not None and not isinstance(result, desired):
                logger.error(f"Type mismatch for key '{k}': expected {desired.__name__}, got {type(result).__name__}")
                results.append(None)
            else:
                results.append(result)
        return results


@dataclass
class ToolExecutor:
    """A class representing a tool executor with a sequence of tools to execute.

    This class manages a sequence of tools and provides methods to inject tools and data into a module, execute the tools,
    and retrieve specific outputs.
    """

    collector: ResultCollector = field(default_factory=ResultCollector)

    collector_name: ClassVar[str] = "collector"

    fn_name: ClassVar[str] = "execute"
    """The name of the function to execute."""

    candidates: List[Tool] = field(default_factory=list)
    """The sequence of tools to execute."""

    data: Dict[str, Any] = field(default_factory=dict)
    """The data that could be used when invoking the tools."""

    def inject_tools[C: Dict[str, Any]](self, cxt: Optional[C] = None) -> C:
        """Inject the tools into the provided module or default.

        This method injects the tools into the provided module or creates a new module if none is provided.
        It checks for potential collisions before injecting to avoid overwriting existing keys and raises KeyError.

        Args:
            cxt (Optional[M]): The module to inject tools into. If None, a new module is created.

        Returns:
            M: The module with injected tools.

        Raises:
            KeyError: If a tool name already exists in the context.
        """
        cxt = cxt or {}
        for tool in self.candidates:
            logger.debug(f"Injecting tool: {tool.name}")
            if tool.name in cxt:
                raise KeyError(f"Collision detected when injecting tool '{tool.name}'")
            cxt[tool.name] = tool.invoke
        return cxt

    def inject_data[C: Dict[str, Any]](self, cxt: Optional[C] = None) -> C:
        """Inject the data into the provided module or default.

        This method injects the data into the provided module or creates a new module if none is provided.
        It checks for potential collisions before injecting to avoid overwriting existing keys and raises KeyError.

        Args:
            cxt (Optional[M]): The module to inject data into. If None, a new module is created.

        Returns:
            M: The module with injected data.

        Raises:
            KeyError: If a data key already exists in the context.
        """
        cxt = cxt or {}
        for key, value in self.data.items():
            logger.debug(f"Injecting data: {key}")
            if key in cxt:
                raise KeyError(f"Collision detected when injecting data key '{key}'")
            cxt[key] = value
        return cxt

    def inject_collector[C: Dict[str, Any]](self, cxt: Optional[C] = None) -> C:
        """Inject the collector into the provided module or default.

        This method injects the collector into the provided module or creates a new module if none is provided.
        It checks for potential collisions before injecting to avoid overwriting existing keys and raises KeyError.

        Args:
            cxt (Optional[M]): The module to inject the collector into. If None, a new module is created.

        Returns:
            M: The module with injected collector.

        Raises:
            KeyError: If the collector name already exists in the context.
        """
        cxt = cxt or {}
        if self.collector_name in cxt:
            raise KeyError(f"Collision detected when injecting collector with name '{self.collector_name}'")
        cxt[self.collector_name] = self.collector
        return cxt

    async def execute[C: Dict[str, Any]](self, body: str, cxt: Optional[C] = None) -> ResultCollector:
        """Execute the sequence of tools with the provided context.

        This method executes the tools in the sequence with the provided context.

        Args:
            body (str): The source code to execute.
            cxt (Optional[C]): The context to execute the tools with. If None, an empty dictionary is used.

        Returns:
            C: The context after executing the tools.
        """
        cxt = self.inject_collector(cxt)
        cxt = self.inject_tools(cxt)
        cxt = self.inject_data(cxt)
        exec(self.assemble(body), cxt)  # noqa: S102
        compiled_fn = cxt[self.fn_name]
        await compiled_fn()
        return self.collector

    def header(self) -> str:
        """Generate the header for the source code."""
        arg_parts = [f'{k}:"{v.__class__.__name__}" = {k}' for k, v in self.data.items()]
        args_str = ", ".join(arg_parts)
        return f"async def {self.fn_name}({args_str})->None:"

    def assemble(self, body: str) -> str:
        """Assemble the source code with the provided context.

        This method assembles the source code by injecting the tools and data into the context.

        Args:
            body (str): The source code to assemble.

        Returns:
            str: The assembled source code.
        """
        return f"{self.header()}\n{self._indent(body)}"

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
