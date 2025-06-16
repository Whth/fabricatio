"""Tests for the tool."""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict
from unittest.mock import MagicMock, patch

import pytest
from fabricatio_tool.models.tool import ResultCollector, Tool, ToolBox, ToolExecutor


# Fixtures
@dataclass
class SampleData:
    value: int = 42


@pytest.fixture
def sample_func():
    def func(x: int, y: str) -> str:
        """Sample function for testing."""
        return f"{x}{y}"

    return func


@pytest.fixture
def tool(sample_func):
    return Tool(source=sample_func, name="test_tool", description="Test tool description")


@pytest.fixture
def toolbox():
    return ToolBox(name="test_box", description="Test toolbox")


@pytest.fixture
def result_collector():
    return ResultCollector()


@pytest.fixture
def tool_executor():
    return ToolExecutor()


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
        assert tool.name == "func"
        assert tool.description == "Sample function for testing."

    def test_invoke_logs(self, tool, caplog) -> None:
        """Test tool invocation logging."""
        with caplog.at_level(logging.INFO):
            tool.invoke(5, "a")
        assert "Invoking tool: test_tool" in caplog.text

    def test_signature_property(self, tool) -> None:
        """Test signature formatting."""
        assert tool.signature == "def test_tool(x: int, y: str) -> str:"

    def test_briefing_property(self, tool) -> None:
        """Test briefing generation."""
        expected = '''def test_tool(x: int, y: str) -> str:
    """
    Test tool description
    """'''
        assert tool.briefing == expected


class TestToolBox:
    """Test cases for the ToolBox class."""

    def test_add_tool(self, toolbox, sample_func: Callable[[int, str], str]) -> None:
        """Test tool addition with decorator."""

        @toolbox.add_tool
        def test_func() -> None:
            pass

        assert len(toolbox.tools) == 1
        assert toolbox.tools[0].name == "test_func"

    def test_get_tool(self, toolbox, sample_func: Callable[[int, str], str]) -> None:
        """Test tool retrieval by name."""
        toolbox.add_tool(sample_func)
        retrieved = toolbox.get("func")
        assert retrieved is not None
        assert retrieved.name == "func"

    def test_briefing_property(self, toolbox, sample_func: Callable[[int, str], str]) -> None:
        """Test toolbox briefing generation."""
        toolbox.add_tool(sample_func)
        expected = """## test_box: Test toolbox
## 1 tools available:
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

    def test_take_missing_key(self, result_collector, caplog) -> None:
        """Test missing key handling with logging."""
        with caplog.at_level(logging.WARNING):
            result_collector.revoke("missing")
        assert "Key 'missing' not found in container." in caplog.text


class TestToolExecutor:
    """Test cases for the ToolExecutor class."""

    @pytest.fixture
    def mock_context(self):
        return {"existing": "value"}

    def test_inject_tools(
        self, tool_executor: ToolExecutor, mock_context: Dict[str, Any], sample_func: Callable[[int, str], str]
    ) -> None:
        """Test tool injection into context."""
        tool = Tool(source=sample_func)
        tool_executor.candidates = [tool]
        new_context = tool_executor.inject_tools(mock_context)
        assert "func" in new_context
        assert new_context["func"](5, "a") == "5a"

    def test_inject_data(self, tool_executor: ToolExecutor, mock_context: Dict[str, Any]) -> None:
        """Test data injection into context."""
        tool_executor.data = {"new": "data"}
        new_context = tool_executor.inject_data(mock_context)
        assert new_context["new"] == "data"

    def test_signature_generation(self, tool_executor) -> None:
        """Test signature generation for executor function."""
        tool_executor.data = {"x": 5}
        assert tool_executor.signature() == 'async def execute(x:"int" = x)->None:'

    @pytest.mark.asyncio
    async def test_execute_with_mocked_code(self, tool_executor:ToolExecutor) -> None:
        """Test code execution with mocked context."""

        source=(f"{tool_executor.collector_varname}.submit('num', 1)\n"
                "")
        col=await tool_executor.execute(source)
        assert col.take("num", int) == {"num":1}



def test_from_recipe(toolbox, sample_func: Callable[[int, str], str]) -> None:
    """Test ToolExecutor creation from recipe."""
    toolbox.add_tool(sample_func)
    executor = ToolExecutor.from_recipe(["func"], [toolbox])
    assert len(executor.candidates) == 1
    assert executor.candidates[0].name == "func"
