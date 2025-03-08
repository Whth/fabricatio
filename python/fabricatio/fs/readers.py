"""Filesystem readers for Fabricatio."""

from pathlib import Path
from typing import Dict

from magika import Magika
from orjson import orjson

from fabricatio.config import configs
from fabricatio.journal import logger

magika = Magika(model_dir=configs.magika.model_dir)


def safe_text_read(path: Path | str) -> str:
    """Safely read the text from a file.

    Args:
        path (Path|str): The path to the file.

    Returns:
        str: The text from the file.
    """
    path = Path(path)
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError) as e:
        logger.error(f"Failed to read file {path}: {e!s}")
        return ""


def safe_json_read(path: Path | str) -> Dict:
    """Safely read the JSON from a file.

    Args:
        path (Path|str): The path to the file.

    Returns:
        dict: The JSON from the file.
    """
    path = Path(path)
    try:
        return orjson.loads(path.read_text(encoding="utf-8"))
    except (orjson.JSONDecodeError, IsADirectoryError, FileNotFoundError) as e:
        logger.error(f"Failed to read file {path}: {e!s}")
        return {}
