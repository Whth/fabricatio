"""This module defines two abstract base classes, `FromMapping` and `FromSequence`.

`FromMapping` provides a method to generate a list of objects from a mapping,
while `FromSequence` provides a method to generate a list of objects from a sequence.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any


class FromMapping[V, T](ABC):
    """Class that provides a method to generate a list of objects from a mapping."""

    @classmethod
    @abstractmethod
    def from_mapping(cls, mapping: Mapping[str, V], /, **kwargs: Any) -> list[T]:
        """Generate a list of objects from a mapping."""


class FromSequence[V](ABC):
    """Class that provides a method to generate a list of objects from a sequence."""

    @classmethod
    @abstractmethod
    def from_sequence[S](cls: type[S], sequence: Sequence[V], /, **kwargs: Any) -> list[S]:
        """Generate a list of objects from a sequence."""
