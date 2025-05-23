"""This module defines two abstract base classes, `FromMapping` and `FromSequence`.

`FromMapping` provides a method to generate a list of objects from a mapping,
while `FromSequence` provides a method to generate a list of objects from a sequence.
"""

from abc import abstractmethod
from typing import Any, List, Mapping, Sequence


class FromMapping:
    """Class that provides a method to generate a list of objects from a mapping."""

    @classmethod
    @abstractmethod
    def from_mapping[S](cls: S, mapping: Mapping[str, Any], **kwargs: Any) -> List[S]:
        """Generate a list of objects from a mapping."""


class FromSequence:
    """Class that provides a method to generate a list of objects from a sequence."""

    @classmethod
    @abstractmethod
    def from_sequence[S](cls: S, sequence: Sequence[Any], **kwargs: Any) -> List[S]:
        """Generate a list of objects from a sequence."""
