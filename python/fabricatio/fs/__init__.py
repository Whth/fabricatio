"""FileSystem manipulation module for Fabricatio."""

from fabricatio.fs.curd import (
    absolute_path,
    copy_file,
    create_directory,
    delete_directory,
    delete_file,
    dump_text,
    gather_files,
    move_file,
    tree,
)
from fabricatio.fs.readers import MAGIKA, safe_json_read, safe_text_read

__all__ = [
    "MAGIKA",
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
    "tree",
]
