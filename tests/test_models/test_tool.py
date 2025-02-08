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
    toolbox = ToolBox(name="test_toolbox", description="test toolbox desc")

    @toolbox.collect_tool
    def test_func():
        return "called"

    assert toolbox.invoke_tool("test_func") == "called"


def test_tool_briefing():
    def test_tool():
        """This is a test function."""
        return "called"

    tool = Tool(source=test_tool)
    expected_briefing = "test_tool() -> None\nThis is a test function."
    assert tool.briefing == expected_briefing


def test_toolbox_briefing():
    toolbox = ToolBox(name="test_toolbox", description="test toolbox desc")

    @toolbox.collect_tool
    def test_func1():
        """This is test function 1."""
        return "called1"

    @toolbox.collect_tool
    def test_func2():
        """This is test function 2."""
        return "called2"

    expected_briefing = (
        "## test_toolbox: test toolbox desc\n"
        "## 2 tools available:\n\n"
        "- test_func1() -> None\nThis is test function 1.\n\n"
        "- test_func2() -> None\nThis is test function 2."
    )
    assert toolbox.briefing == expected_briefing
