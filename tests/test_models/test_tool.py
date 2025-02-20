"""Tests for the tool module."""

from fabricatio.models.tool import Tool, ToolBox


def test_tool_initialization():
    tool = Tool(name="Test Tool", description="Test Tool Description", source=lambda x: x)
    assert tool.name == "Test Tool"
    assert tool.description == "Test Tool Description"


def test_tool_invoke():
    tool = Tool(name="Test Tool", description="Test Tool Description", source=lambda x: x)
    result = tool.invoke("test input")
    assert result == "test input"


def test_toolbox_initialization():
    toolbox = ToolBox(
        name="Test Toolbox",
        description="Test Toolbox Description",
        tools=[Tool(name="Test Tool", description="Test Tool Description", source=lambda x: x)],
    )
    assert toolbox.name == "Test Toolbox"
    assert toolbox.description == "Test Toolbox Description"
    assert len(toolbox.tools) == 1


def test_toolbox_add_tool():
    toolbox = ToolBox(name="Test Toolbox", description="Test Toolbox Description")

    def test_tool(x):
        return x

    toolbox.add_tool(test_tool)
    assert len(toolbox.tools) == 1


def test_toolbox_remove_tool():
    toolbox = ToolBox(
        name="Test Toolbox",
        description="Test Toolbox Description",
        tools=[Tool(name="Test Tool", description="Test Tool Description", source=lambda x: x)],
    )
    toolbox.tools.remove(toolbox.tools[0])
    assert len(toolbox.tools) == 0


def test_tool_briefing():
    tool = Tool(name="Test Tool", description="Test Tool Description", source=lambda x: x)
    briefing = tool.briefing
    assert "def Test Tool" in briefing
    assert "Test Tool Description" in briefing


def test_toolbox_briefing():
    toolbox = ToolBox(
        name="Test Toolbox",
        description="Test Toolbox Description",
        tools=[Tool(name="Test Tool", description="Test Tool Description", source=lambda x: x)],
    )
    briefing = toolbox.briefing
    assert "Test Toolbox" in briefing
    assert "Test Tool" in briefing
