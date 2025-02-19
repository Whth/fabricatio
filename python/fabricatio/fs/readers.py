"""Filesystem readers for Fabricatio."""

from pathlib import Path

from magika import Magika

from fabricatio.config import configs

magika = Magika(model_dir=configs.magika.model_dir)


def safe_text_read(path: Path) -> str:
    """Safely read the text from a file.

    Args:
        path (Path): The path to the file.

    Returns:
        str: The text from the file.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
        return ""
