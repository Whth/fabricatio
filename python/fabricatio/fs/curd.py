"""File system create, update, read, delete operations."""

import shutil
import subprocess
from pathlib import Path
from typing import Union

from fabricatio.decorators import confirm_to_execute, depend_on_external_cmd
from fabricatio.journal import logger


@confirm_to_execute
def copy_file(src: Union[str, Path], dst: Union[str, Path]) -> None:
    """Copy a file from source to destination.

    Args:
        src: Source file path
        dst: Destination file path

    Raises:
        FileNotFoundError: If source file doesn't exist
        shutil.SameFileError: If source and destination are the same
    """
    try:
        shutil.copy(src, dst)
        logger.info(f"Copied file from {src} to {dst}")
    except OSError as e:
        logger.error(f"Failed to copy file from {src} to {dst}: {e!s}")
        raise


@confirm_to_execute
def move_file(src: Union[str, Path], dst: Union[str, Path]) -> None:
    """Move a file from source to destination.

    Args:
        src: Source file path
        dst: Destination file path

    Raises:
        FileNotFoundError: If source file doesn't exist
        shutil.SameFileError: If source and destination are the same
    """
    try:
        shutil.move(src, dst)
        logger.info(f"Moved file from {src} to {dst}")
    except OSError as e:
        logger.error(f"Failed to move file from {src} to {dst}: {e!s}")
        raise


@confirm_to_execute
def delete_file(file_path: Union[str, Path]) -> None:
    """Delete a file.

    Args:
        file_path: Path to the file to be deleted

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If no permission to delete the file
    """
    try:
        Path(file_path).unlink()
        logger.info(f"Deleted file: {file_path}")
    except OSError as e:
        logger.error(f"Failed to delete file {file_path}: {e!s}")
        raise


@confirm_to_execute
def create_directory(dir_path: Union[str, Path], parents: bool = True, exist_ok: bool = True) -> None:
    """Create a directory.

    Args:
        dir_path: Path to the directory to create
        parents: Create parent directories if they don't exist
        exist_ok: Don't raise error if directory already exists
    """
    try:
        Path(dir_path).mkdir(parents=parents, exist_ok=exist_ok)
        logger.info(f"Created directory: {dir_path}")
    except OSError as e:
        logger.error(f"Failed to create directory {dir_path}: {e!s}")
        raise


@confirm_to_execute
@depend_on_external_cmd(
    "erd",
    "Please install `erd` using `cargo install erdtree` or `scoop install erdtree`.",
    "https://github.com/solidiquis/erdtree",
)
def tree(dir_path: Union[str, Path]) -> str:
    """Generate a tree representation of the directory structure. Requires `erd` to be installed."""
    dir_path = Path(dir_path)
    return subprocess.check_output(("erd", dir_path.as_posix()), encoding="utf-8")  # noqa: S603


@confirm_to_execute
def delete_directory(dir_path: Union[str, Path]) -> None:
    """Delete a directory and its contents.

    Args:
        dir_path: Path to the directory to delete

    Raises:
        FileNotFoundError: If directory doesn't exist
        OSError: If directory is not empty and can't be removed
    """
    try:
        shutil.rmtree(dir_path)
        logger.info(f"Deleted directory: {dir_path}")
    except OSError as e:
        logger.error(f"Failed to delete directory {dir_path}: {e!s}")
        raise
