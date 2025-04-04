"""Filesystem readers for Fabricatio."""

from pathlib import Path
from typing import Dict, List, Tuple

import orjson
import regex
from magika import Magika

from fabricatio.config import configs
from fabricatio.journal import logger

MAGIKA = Magika(model_dir=configs.magika.model_dir)


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


def extract_sections(string: str, level: int, section_char: str = "#") -> List[Tuple[str, str]]:
    """Extract sections from markdown-style text by header level.

    Args:
        string (str): Input text to parse
        level (int): Header level (e.g., 1 for '#', 2 for '##')
        section_char (str, optional): The character used for headers (default: '#')

    Returns:
        List[Tuple[str, str]]: List of (header_text, section_content) tuples
    """
    return regex.findall(
        r"^%s{%d}\s+(.+?)\n((?:(?!^%s{%d}\s).|\n)*)" % (section_char, level, section_char, level),
        string,
        regex.MULTILINE,
    )
