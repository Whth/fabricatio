from fabricatio.models.tool import Tool, ToolBox


def test_tool_call():
    def test_func():
        return "called"

    tool = Tool(source=test_func, name="test_tool")
    assert tool() == "called"


def test_toolbox_collect_tool():
    toolbox = ToolBox(name="test_toolbox", description="test toolbox desc")

    @toolbox.collect_tool
    def test_func():
        return "called"

    assert len(toolbox.tools) == 1
    assert toolbox.tools[0].name == "test_func"


def test_toolbox_invoke_tool():
    toolbox = ToolBox()

    @toolbox.collect_tool
    def test_func():
        return "called"

    assert toolbox.invoke_tool("test_func") == "called"
