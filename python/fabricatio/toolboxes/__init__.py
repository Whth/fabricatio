"""Contains the built-in toolboxes for the Fabricatio package."""

from typing import Set

from fabricatio.models.tool import ToolBox
from fabricatio.toolboxes.arithmetic import arithmetic_toolbox
from fabricatio.toolboxes.fs import fs_toolbox
from fabricatio.toolboxes.task import task_toolbox

basic_toolboxes: Set[ToolBox] = {task_toolbox, arithmetic_toolbox}

__all__ = [
    "arithmetic_toolbox",
    "basic_toolboxes",
    "fs_toolbox",
    "task_toolbox",
]
