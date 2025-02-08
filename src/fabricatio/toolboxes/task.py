from fabricatio.models.task import Task
from fabricatio.models.tool import ToolBox

TaskToolBox = ToolBox(name="TaskToolBox", description="A toolbox for tasks management.").add_tool(Task.simple_task)
