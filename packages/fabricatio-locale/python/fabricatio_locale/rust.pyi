"""Rust bindings for the Rust API of fabricatio-locale."""

from pathlib import Path
from typing import List

class Msg:
    """Represents a message entry in a .po file."""

    id: str
    txt: str
    def __init__(self, *, id: str, txt: str) -> None: ...

def read_pofile(file_path: Path | str) -> List[Msg]:
    """Reads a .po file and returns a list of Message objects containing msgid and msgstr.

    Args:
        file_path: Path to the .po file to be read.

    Returns:
        A list of Message objects, each representing a message entry from the .po file.

    Raises:
        PyRuntimeError: If there is an error parsing the .po file.
    """

def update_pofile(file_path: Path | str, messages: List[Msg]) -> None:
    """Updates a .po file with the provided messages.

    Args:
        file_path: Path to the .po file to be updated.
        messages: A list of Message objects containing msgid and msgstr values to update or add.

    Raises:
        PyRuntimeError: If there is an error reading, updating, or writing the .po file.
    """
