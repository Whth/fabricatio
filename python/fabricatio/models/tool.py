"""A module for defining tools and toolboxes.

This module provides classes for defining tools and toolboxes, which can be used to manage and execute callable functions
with additional functionalities such as logging, execution info, and briefing.
"""

from importlib.machinery import ModuleSpec
from importlib.util import module_from_spec
from inspect import iscoroutinefunction, signature
from types import CodeType, ModuleType
from typing import Any, Callable, Dict, List, Optional, Self, cast, overload

from fabricatio.config import configs
from fabricatio.decorators import logging_execution_info, use_temp_module
from fabricatio.journal import logger
from fabricatio.models.generic import WithBriefing
from pydantic import BaseModel, ConfigDict, Field


class Tool[**P, R](WithBriefing):
    """A class representing a tool with a callable source function.

    This class encapsulates a callable function (source) and provides methods to invoke it, log its execution, and generate
    a brief description (briefing) of the tool.

    Attributes:
        name (str): The name of the tool.
        description (str): The description of the tool.
        source (Callable[P, R]): The source function of the tool.
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

    Attributes:
        description (str): The description of the toolbox.
        tools (List[Tool]): A list of tools in the toolbox.
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


class ToolExecutor(BaseModel):
    """A class representing a tool executor with a sequence of tools to execute.

    This class manages a sequence of tools and provides methods to inject tools and data into a module, execute the tools,
    and retrieve specific outputs.

    Attributes:
        candidates (List[Tool]): The sequence of tools to execute.
        data (Dict[str, Any]): The data that could be used when invoking the tools.
    """
    model_config = ConfigDict(use_attribute_docstrings=True)
    candidates: List[Tool] = Field(default_factory=list, frozen=True)
    """The sequence of tools to execute."""

    data: Dict[str, Any] = Field(default_factory=dict)
    """The data that could be used when invoking the tools."""

    def inject_tools[M: ModuleType](self, module: Optional[M] = None) -> M:
        """Inject the tools into the provided module or default.

        This method injects the tools into the provided module or creates a new module if none is provided.

        Args:
            module (Optional[M]): The module to inject tools into. If None, a new module is created.

        Returns:
            M: The module with injected tools.
        """
        module = module or cast(
            "M", module_from_spec(spec=ModuleSpec(name=configs.toolbox.tool_module_name, loader=None))
        )
        for tool in self.candidates:
            logger.debug(f"Injecting tool: {tool.name}")
            setattr(module, tool.name, tool.invoke)
        return module

    def inject_data[M: ModuleType](self, module: Optional[M] = None) -> M:
        """Inject the data into the provided module or default.

        This method injects the data into the provided module or creates a new module if none is provided.

        Args:
            module (Optional[M]): The module to inject data into. If None, a new module is created.

        Returns:
            M: The module with injected data.
        """
        module = module or cast(
            'M', module_from_spec(spec=ModuleSpec(name=configs.toolbox.data_module_name, loader=None))
        )
        for key, value in self.data.items():
            logger.debug(f"Injecting data: {key}")
            setattr(module, key, value)
        return module

    def execute[C: Dict[str, Any]](self, source: CodeType, cxt: Optional[C] = None) -> C:
        """Execute the sequence of tools with the provided context.

        This method executes the tools in the sequence with the provided context.

        Args:
            source (CodeType): The source code to execute.
            cxt (Optional[C]): The context to execute the tools with. If None, an empty dictionary is used.

        Returns:
            C: The context after executing the tools.
        """
        cxt = cxt or {}

        @use_temp_module([self.inject_data(), self.inject_tools()])
        def _exec() -> None:
            exec(source, cxt)  # noqa: S102

        _exec()
        return cxt

    @overload
    def take[C: Dict[str, Any]](self, keys: List[str], source: CodeType, cxt: Optional[C] = None) -> C:
        """Check the output of the tools with the provided context.

        This method executes the tools and retrieves specific keys from the context.

        Args:
            keys (List[str]): The keys to retrieve from the context.
            source (CodeType): The source code to execute.
            cxt (Optional[C]): The context to execute the tools with. If None, an empty dictionary is used.

        Returns:
            C: A dictionary containing the retrieved keys and their values.
        """
        ...

    @overload
    def take[C: Dict[str, Any]](self, keys: str, source: CodeType, cxt: Optional[C] = None) -> Any:
        """Check the output of the tools with the provided context.

        This method executes the tools and retrieves a specific key from the context.

        Args:
            keys (str): The key to retrieve from the context.
            source (CodeType): The source code to execute.
            cxt (Optional[C]): The context to execute the tools with. If None, an empty dictionary is used.

        Returns:
            Any: The value of the retrieved key.
        """
        ...

    def take[C: Dict[str, Any]](self, keys: List[str] | str, source: CodeType, cxt: Optional[C] = None) -> C | Any:
        """Check the output of the tools with the provided context.

        This method executes the tools and retrieves specific keys or a specific key from the context.

        Args:
            keys (List[str] | str): The keys to retrieve from the context. Can be a single key or a list of keys.
            source (CodeType): The source code to execute.
            cxt (Optional[C]): The context to execute the tools with. If None, an empty dictionary is used.

        Returns:
            C | Any: A dictionary containing the retrieved keys and their values, or the value of the retrieved key.
        """
        cxt = self.execute(source, cxt)
        if isinstance(keys, str):
            return cxt[keys]
        return {key: cxt[key] for key in keys}

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
