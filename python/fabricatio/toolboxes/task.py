"""This module contains the toolbox for tasks management."""

from fabricatio.models.task import Task
from fabricatio.models.tool import ToolBox

task_toolbox = ToolBox(name="TaskToolBox", description="A toolbox for tasks management.").add_tool(Task.simple_task)
