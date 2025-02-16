import pytest
from fabricatio.models.tool import Tool, ToolBox

def test_tool_initialization():
    tool = Tool(name="Test Tool", description="Test Tool Description")
    assert tool.name == "Test Tool"
    assert tool.description == "Test Tool Description"

def test_toolbox_initialization():
    toolbox = ToolBox(name="Test Toolbox", description="Test Toolbox Description", tools=[Tool(name="Test Tool", description="Test Tool Description")])
    assert toolbox.name == "Test Toolbox"
    assert toolbox.description == "Test Toolbox Description"
    assert len(toolbox.tools) == 1

def test_toolbox_add_tool():
    toolbox = ToolBox(name="Test Toolbox", description="Test Toolbox Description")
    toolbox.add_tool(Tool(name="Test Tool", description="Test Tool Description"))
    assert len(toolbox.tools) == 1

def test_toolbox_remove_tool():
    toolbox = ToolBox(name="Test Toolbox", description="Test Toolbox Description", tools=[Tool(name="Test Tool", description="Test Tool Description")])
    toolbox.remove_tool(Tool(name="Test Tool", description="Test Tool Description"))
    assert len(toolbox.tools) == 0

# New test cases
def test_tool_execution():
    tool = Tool(name="Test Tool", description="Test Tool Description", source=lambda x: x)
    result = tool.invoke("test input")
    assert result == "test input"

def test_toolbox_generate_prompt():
    toolbox = ToolBox(name="Test Toolbox", description="Test Toolbox Description", tools=[Tool(name="Test Tool", description="Test Tool Description", source=lambda x: x)])
    prompt = toolbox.generate_prompt()
    # Add assertions based on expected behavior