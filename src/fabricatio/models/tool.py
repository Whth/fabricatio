from typing import Callable, ParamSpecArgs, Set

from fabricatio.models.generic import Named, Described


class ToolBox(Named, Described):
    ToolSet: Set[Named] =

    def register_tool(self, tool: Callable[[ParamSpecArgs], ToolSet]):
        self.ToolSet[self.name] = tool
        return tool
