"""FileSystem manipulation module for Fabricatio."""

from fabricatio_tool.fs.curd import (
    absolute_path,
    copy_file,
    create_directory,
    delete_directory,
    delete_file,
    dump_text,
    gather_files,
    move_file,
)
from fabricatio_tool.fs.readers import safe_json_read, safe_text_read
from fabricatio_tool.rust import treeview

__all__ = [
    "absolute_path",
    "copy_file",
    "create_directory",
    "delete_directory",
    "delete_file",
    "dump_text",
    "gather_files",
    "move_file",
    "safe_json_read",
    "safe_text_read",
    "treeview",
]
