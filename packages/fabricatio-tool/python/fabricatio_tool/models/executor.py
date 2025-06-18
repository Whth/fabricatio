"""Module containing the ToolExecutor class for managing and executing a sequence of tools."""

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Self

from fabricatio_core import logger

from fabricatio_tool.config import tool_config
from fabricatio_tool.models.collector import ResultCollector
from fabricatio_tool.models.tool import Tool, ToolBox
from fabricatio_tool.rust import CheckConfig, gather_violations


@dataclass
class ToolExecutor:
    """A class representing a tool executor with a sequence of tools to execute.

    This class manages a sequence of tools and provides methods to inject tools and data into a module, execute the tools,
    and retrieve specific outputs.
    """

    collector: ResultCollector = field(default_factory=ResultCollector)

    collector_varname: ClassVar[str] = "collector"

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
        if self.collector_varname in cxt:
            raise KeyError(f"Collision detected when injecting collector with name '{self.collector_varname}'")
        cxt[self.collector_varname] = self.collector
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
        source = self.assemble(body)
        if vio := gather_violations(
            source,
            CheckConfig(*tool_config.check_modules),
            CheckConfig(*tool_config.check_imports),
            self._make_calls_check_config(),
        ):
            raise ValueError(f"Violations found in code: \n{source}\n\n{'\n'.join(vio)}")

        exec(source, cxt)  # noqa: S102
        compiled_fn = cxt[self.fn_name]
        await compiled_fn()
        return self.collector

    def _make_calls_check_config(self) -> CheckConfig:
        """Generate the check configuration for the calls."""
        if tool_config.check_calls.mode == "whitelist":
            targets = {tool.name for tool in self.candidates}
            targets.update(tool_config.check_calls.targets)
            return CheckConfig(
                mode="whitelist",
                targets=targets,
            )
        if tool_config.check_calls.mode == "blacklist":
            return CheckConfig(*tool_config.check_calls)
        raise ValueError(f"Unknown mode: {tool_config.check_calls.mode}")

    def signature(self) -> str:
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
        return f"{self.signature()}\n{self._indent(body)}"

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
        while recipe:
            tool_name = recipe.pop(0)
            for toolbox in toolboxes:
                tool = toolbox.get(tool_name)
                if tool is None:
                    logger.warning(f"Tool {tool_name} not found in any toolbox.")
                    continue
                tools.append(tool)
                break
        return cls(candidates=tools)
