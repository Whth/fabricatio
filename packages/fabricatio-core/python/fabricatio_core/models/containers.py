"""Container models for fabricatio-core.

This module provides data structures for representing various container
types used in the fabrication process, including code snippets and
other configurable components.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodeSnippet:
    """Code snippet."""

    source: str

    write_to: str | Path

    def write(self) -> None:
        """Write the source code to a file."""
        p = Path(self.write_to)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.source, encoding="utf-8", newline="\n")
