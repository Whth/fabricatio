"""File system tool box."""

from fabricatio.fs.curd import copy_file, create_directory, delete_directory, delete_file, dump_text, move_file, tree
from fabricatio.models.tool import ToolBox

fs_toolbox = (
    ToolBox(name="FsToolBox", description="A toolbox for basic file system operations.")
    .add_tool(dump_text)
    .add_tool(copy_file)
    .add_tool(move_file)
    .add_tool(delete_file)
    .add_tool(tree)
    .add_tool(delete_directory)
    .add_tool(create_directory)
)
