"""Module containing the ToolExecutor class for managing and executing a sequence of tools."""

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Self

from fabricatio_core import logger

from fabricatio_tool.config import CheckConfigModel, tool_config
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

    async def execute[C: Dict[str, Any]](
        self,
        body: str,
        cxt: Optional[C] = None,
        check_modules: Optional[CheckConfigModel] = None,
        check_imports: Optional[CheckConfigModel] = None,
        check_calls: Optional[CheckConfigModel] = None,
    ) -> ResultCollector:
        """Execute the sequence of tools with the provided context.

        This method orchestrates the execution process by injecting the collector, tools, and data into the context,
        assembling the source code, checking for violations, and finally executing the compiled function.

        Args:
            body (str): The source code to execute.
            cxt (Optional[C]): The context to execute the tools with. If None, an empty dictionary is used.
            check_modules (Optional[CheckConfigModel]): Configuration for module-related checks.
            check_imports (Optional[CheckConfigModel]): Configuration for import-related checks.
            check_calls (Optional[CheckConfigModel]): Configuration for call-related checks.

        Returns:
            ResultCollector: The collector containing results from the executed tools.
        """
        cxt = self.inject_collector(cxt)
        cxt = self.inject_tools(cxt)
        cxt = self.inject_data(cxt)
        source = self.assemble(body)
        if vio := gather_violations(
            source,
            CheckConfig(**(check_modules or tool_config.check_modules).model_dump()),
            CheckConfig(**(check_imports or tool_config.check_imports).model_dump()),
            CheckConfig(**self.validate_callcheck_config(check_calls or tool_config.check_calls).model_dump()),
        ):
            raise ValueError(f"Violations found in code: \n{source}\n\n{'\n'.join(vio)}")
        logger.debug(f"Starting compile and execution of function: \n{source}")
        exec(source, cxt)  # noqa: S102
        compiled_fn = cxt[self.fn_name]
        await compiled_fn()
        return self.collector

    def validate_callcheck_config(self, check_calls: CheckConfigModel) -> CheckConfigModel:
        """Validate the call check configuration.

        This method ensures that the tools defined in the executor are properly accounted for in the call check configuration.
        If the configuration is in blacklist mode and any tool names appear in the targets, a ValueError is raised.
        Otherwise, all tool names are added to the targets in whitelist mode.

        Args:
            check_calls (CheckConfigModel): The call check configuration to validate and update.

        Returns:
            CheckConfigModel: The validated and potentially updated call check configuration.

        Raises:
            ValueError: If blacklist mode is used and any tool names are found in the targets.
        """
        check_calls = check_calls.model_copy(deep=True)

        if check_calls.is_blacklist() and any(
            included := [tool.name for tool in self.candidates if tool.name in check_calls.targets]
        ):
            raise ValueError(f"Blacklist mode is not allowed for tools: {included}")

        for tool in self.candidates:
            logger.info(f"Adding tool {tool.name} to callcheck targets whitelist.")
            check_calls.targets.add(tool.name)
        return check_calls

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
                    logger.warn(f"Tool {tool_name} not found in any toolbox.")
                    continue
                tools.append(tool)
                break
        return cls(candidates=tools)
