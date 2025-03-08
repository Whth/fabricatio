"""A module for defining tools and toolboxes."""

from importlib.machinery import ModuleSpec
from importlib.util import module_from_spec
from inspect import iscoroutinefunction, signature
from types import CodeType, ModuleType
from typing import Any, Callable, Dict, List, Optional, Self, overload

from fabricatio.config import configs
from fabricatio.decorators import logging_execution_info, use_temp_module
from fabricatio.journal import logger
from fabricatio.models.generic import WithBriefing
from pydantic import BaseModel, ConfigDict, Field


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

        if not self.name:
            raise RuntimeError("The tool must have a source function.")

        self.description = self.description or self.source.__doc__ or ""
        self.description = self.description.strip()

    def invoke(self, *args: P.args, **kwargs: P.kwargs) -> R:
        """Invoke the tool's source function with the provided arguments."""
        logger.info(f"Invoking tool: {self.name}")
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

    tools: List[Tool] = Field(default_factory=list, frozen=True)
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
        self.collect_tool(logging_execution_info(func))
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
            ValueError: If no tool with the specified name is found.
        """
        tool = next((tool for tool in self.tools if tool.name == name), None)
        if tool is None:
            err = f"No tool with the name {name} found in the toolbox."
            logger.error(err)
            raise ValueError(err)

        return tool

    def __hash__(self) -> int:
        """Return a hash of the toolbox based on its briefing."""
        return hash(self.briefing)


class ToolExecutor(BaseModel):
    """A class representing a tool executor with a sequence of tools to execute."""

    model_config = ConfigDict(use_attribute_docstrings=True)
    candidates: List[Tool] = Field(default_factory=list, frozen=True)
    """The sequence of tools to execute."""

    data: Dict[str, Any] = Field(default_factory=dict)
    """The data that could be used when invoking the tools."""

    def inject_tools[M: ModuleType](self, module: Optional[M] = None) -> M:
        """Inject the tools into the provided module or default."""
        module = module or module_from_spec(spec=ModuleSpec(name=configs.toolbox.tool_module_name, loader=None))
        for tool in self.candidates:
            logger.debug(f"Injecting tool: {tool.name}")
            setattr(module, tool.name, tool.invoke)
        return module

    def inject_data[M: ModuleType](self, module: Optional[M] = None) -> M:
        """Inject the data into the provided module or default."""
        module = module or module_from_spec(spec=ModuleSpec(name=configs.toolbox.data_module_name, loader=None))
        for key, value in self.data.items():
            logger.debug(f"Injecting data: {key}")
            setattr(module, key, value)
        return module

    def execute[C: Dict[str, Any]](self, source: CodeType, cxt: Optional[C] = None) -> C:
        """Execute the sequence of tools with the provided context."""
        cxt = cxt or {}

        @use_temp_module([self.inject_data(), self.inject_tools()])
        def _exec() -> None:
            exec(source, cxt)  # noqa: S102

        _exec()
        return cxt

    @overload
    def take[C: Dict[str, Any]](self, keys: List[str], source: CodeType, cxt: Optional[C] = None) -> C:
        """Check the output of the tools with the provided context."""
        ...

    @overload
    def take[C: Dict[str, Any]](self, keys: str, source: CodeType, cxt: Optional[C] = None) -> Any:
        """Check the output of the tools with the provided context."""
        ...

    def take[C: Dict[str, Any]](self, keys: List[str] | str, source: CodeType, cxt: Optional[C] = None) -> C | Any:
        """Check the output of the tools with the provided context."""
        cxt = self.execute(source, cxt)
        if isinstance(keys, str):
            return cxt[keys]
        return {key: cxt[key] for key in keys}

    @classmethod
    def from_recipe(cls, recipe: List[str], toolboxes: List[ToolBox]) -> Self:
        """Create a tool executor from a recipe and a list of toolboxes."""
        tools = []
        while tool_name := recipe.pop(0):
            for toolbox in toolboxes:
                tools.append(toolbox[tool_name])

        return cls(candidates=tools)
