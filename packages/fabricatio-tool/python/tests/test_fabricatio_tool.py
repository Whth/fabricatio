"""Tests for the tool."""

from dataclasses import dataclass
from typing import Any, Callable, Dict

import pytest
from fabricatio_tool.models.collector import ResultCollector
from fabricatio_tool.models.executor import ToolExecutor
from fabricatio_tool.models.tool import Tool, ToolBox


# Fixtures
@dataclass
class SampleData:
    """A data class for holding a single integer value.

    Attributes:
        value (int): The integer value, default is 42.
    """

    value: int = 42


@pytest.fixture
def sample_func() -> Callable[[int, str], str]:
    """Provides a sample function for testing.

    Returns:
        A function that concatenates an integer and string.
    """

    def func(x: int, y: str) -> str:
        """Sample function for testing.

        Args:
            x: An integer input.
            y: A string input.

        Returns:
            Concatenated result as a string.
        """
        return f"{x}{y}"

    return func


@pytest.fixture
def tool(sample_func: Callable[[int, str], str]) -> Tool:
    """Provides a preconfigured Tool instance.

    Args:
        sample_func: The source function for the tool.

    Returns:
        A configured Tool object.
    """
    return Tool(source=sample_func, name="test_tool", description="Test tool description")


@pytest.fixture
def toolbox(sample_func: Callable[[int, str], str]) -> ToolBox:
    """Provides a preconfigured ToolBox instance.

    Args:
        sample_func: A function to be added as a tool.

    Returns:
        A configured ToolBox object.
    """
    return ToolBox(name="test_box", description="Test toolbox").add_tool(sample_func, confirm=False)


@pytest.fixture
def result_collector() -> ResultCollector:
    """Fixture providing a fresh ResultCollector instance for testing.

    Returns:
        A new instance of ResultCollector.
    """
    return ResultCollector()


@pytest.fixture
def tool_executor(toolbox: ToolBox) -> ToolExecutor:
    """Fixture providing a fresh ToolExecutor instance for testing.

    Returns:
        A new instance of ToolExecutor.
    """
    return ToolExecutor(candidates=toolbox.tools)


class TestTool:
    """Test cases for the Tool class."""

    def test_tool_initialization(self, tool: Tool) -> None:
        """Test Tool initialization and property setup."""
        assert tool.name == "test_tool"
        assert tool.description == "Test tool description"
        assert tool.source(5, "a") == "5a"

    def test_model_post_init(self, sample_func: Callable[[int, str], str]) -> None:
        """Test automatic name/description assignment."""
        tool = Tool(source=sample_func)
        assert tool.name == sample_func.__name__
        assert tool.description == sample_func.__doc__.strip()
        tool = Tool(source=sample_func, description="Custom description")
        assert tool.description == "Custom description"

    def test_signature_property(self, tool: Tool) -> None:
        """Test signature formatting."""
        assert tool.signature == "def test_tool(x: int, y: str) -> str:"

    def test_briefing_property(self, tool: Tool) -> None:
        """Test briefing generation."""
        expected = '''def test_tool(x: int, y: str) -> str:
    """
    Test tool description
    """'''
        assert tool.briefing == expected


class TestToolBox:
    """Test cases for the ToolBox class."""

    def test_add_tool(self, toolbox: ToolBox) -> None:
        """Test tool addition with decorator."""

        @toolbox.add_tool
        def test_func() -> None:
            pass

        assert len(toolbox.tools) == 2
        assert toolbox.tools[-1].name == "test_func"

    def test_get_tool(self, toolbox: ToolBox, sample_func: Callable[[int, str], str]) -> None:
        """Test tool retrieval by name."""
        toolbox.add_tool(sample_func)
        retrieved = toolbox.get("func")
        assert retrieved is not None
        assert retrieved.name == "func"

    def test_briefing_property(self, toolbox: ToolBox, sample_func: Callable[[int, str], str]) -> None:
        """Test toolbox briefing generation."""
        toolbox.add_tool(sample_func)
        expected = """## test_box: Test toolbox
## 2 tools available:
def func(x: int, y: str) -> str:
def func(x: int, y: str) -> str:"""
        assert toolbox.briefing == expected


class TestResultCollector:
    """Test cases for the ResultCollector class."""

    def test_submit_and_revoke(self, result_collector: ResultCollector) -> None:
        """Test value submission and revocation."""
        collector = result_collector.submit("key", 42)
        assert collector.container["key"] == 42
        collector.revoke("key")
        assert "key" not in collector.container

    def test_take_single_key(self, result_collector: ResultCollector) -> None:
        """Test single key retrieval with type checking."""
        result_collector.submit("num", 42)
        assert result_collector.take("num", int) == 42
        assert result_collector.take("num", str) is None

    def test_take_multiple_keys(self, result_collector: ResultCollector) -> None:
        """Test multiple key retrieval with type checking."""
        result_collector.submit("a", 1).submit("b", "2")
        results = result_collector.take(["a", "b"], int)
        assert results == [1, None]


class TestToolExecutor:
    """Test cases for the ToolExecutor class."""

    @pytest.fixture
    def mock_context(self) -> Dict[str, Any]:
        """Mock context for testing."""
        return {"existing": "value"}

    def test_inject_tools(
        self, tool_executor: ToolExecutor, mock_context: Dict[str, Any], sample_func: Callable[[int, str], str]
    ) -> None:
        """Test tool injection into context."""
        new_context = tool_executor.inject_tools(mock_context)
        assert sample_func.__name__ in new_context
        assert new_context[sample_func.__name__](5, "a") == "5a"

    def test_inject_data(self, tool_executor: ToolExecutor, mock_context: Dict[str, Any]) -> None:
        """Test data injection into context."""
        tool_executor.data = {"new": "data"}
        new_context = tool_executor.inject_data(mock_context)
        assert new_context["new"] == "data"

    def test_signature_generation(self, tool_executor: ToolExecutor) -> None:
        """Test signature generation for executor function."""
        tool_executor.data = {"x": 5}
        assert tool_executor.signature() == 'async def execute(x:"int" = x)->None:'

    @pytest.mark.asyncio
    async def test_execute_with_mocked_code(self, tool_executor: ToolExecutor) -> None:
        """Test code execution with mocked context."""
        source = f"x=32*6\n{tool_executor.collector_varname}.submit('num', x)\n"
        col = await tool_executor.execute(source)
        assert col.take("num", int) == 32 * 6

        source = f"import os\nx=32*6\n{tool_executor.collector_varname}.submit('num', x)\n"
        with pytest.raises(ValueError, match="Forbidden import module: os"):
            await tool_executor.execute(source)
        source = f"import os as las\nx=32*6\n{tool_executor.collector_varname}.submit('num', x)\n"
        with pytest.raises(ValueError, match="Forbidden import module: os"):
            await tool_executor.execute(source)
        source = f"from os import path\nx=32*6\n{tool_executor.collector_varname}.submit('num', x)\n"
        with pytest.raises(ValueError, match="Forbidden import module: os"):
            await tool_executor.execute(source)


@pytest.mark.asyncio
async def test_forbidden_import_check(tool_executor: ToolExecutor, sample_func: Callable[[int, str], str]) -> None:
    """Test detection of forbidden imports."""
    source = "import os\nx=32*6"
    with pytest.raises(ValueError, match="Forbidden import module: os"):
        await tool_executor.execute(source)

    source = "from os import path"
    with pytest.raises(ValueError, match="Forbidden import module: os"):
        await tool_executor.execute(source)

    source = "import sys"
    with pytest.raises(ValueError, match="Forbidden import module: sys"):
        await tool_executor.execute(source)
    source = "exec(\"print('hi')\")"
    with pytest.raises(ValueError, match="Forbidden function call: exec()"):
        await tool_executor.execute(source)
    source = "print(\"exec('hi=1')\")"
    with pytest.raises(ValueError, match="Forbidden function call: print()"):
        await tool_executor.execute(source)
    source = f"res={sample_func.__name__}(5, 'a')\n{tool_executor.collector_varname}.submit('result', res)"
    col = await tool_executor.execute(source)
    assert col.take("result") == "5a"

    source = f"res={sample_func.__name__}_var(5, 'a')\n{tool_executor.collector_varname}.submit('result', res)"
    with pytest.raises(ValueError, match=f"Forbidden function call: {sample_func.__name__}_var()"):
        await tool_executor.execute(source)


def test_from_recipe(toolbox: ToolBox, sample_func: Callable[[int, str], str]) -> None:
    """Test ToolExecutor creation from recipe."""
    toolbox.add_tool(sample_func)
    executor = ToolExecutor.from_recipe(["func"], [toolbox])
    assert len(executor.candidates) == 1
    assert executor.candidates[0].name == "func"
