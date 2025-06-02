"""FileSystem manipulation module for Fabricatio."""

from importlib.util import find_spec

from fabricatio_core.fs.curd import (
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
from fabricatio_core.fs.readers import safe_json_read, safe_text_read

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
    "tree",
]

if find_spec("magika"):
    from magika import Magika

    MAGIKA = Magika()
    __all__ += ["MAGIKA"]
