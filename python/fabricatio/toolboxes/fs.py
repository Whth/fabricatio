"""File system tool box."""

from fabricatio.fs import (
    absolute_path,
    copy_file,
    create_directory,
    delete_directory,
    delete_file,
    dump_text,
    gather_files,
    move_file,
    safe_json_read,
    safe_text_read,
    tree,
)
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
    .add_tool(absolute_path)
    .add_tool(safe_text_read)
    .add_tool(safe_json_read)
    .add_tool(gather_files)
)
