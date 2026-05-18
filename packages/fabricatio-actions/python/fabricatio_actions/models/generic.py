"""This module defines two abstract base classes, `FromMapping` and `FromSequence`.

`FromMapping` provides a method to generate a list of objects from a mapping,
while `FromSequence` provides a method to generate a list of objects from a sequence.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Mapping, Sequence, Type


class FromMapping[V, T](ABC):
    """Class that provides a method to generate a list of objects from a mapping."""

    @classmethod
    @abstractmethod
    def from_mapping(cls, mapping: Mapping[str, V], /, **kwargs: Any) -> List[T]:
        """Generate a list of objects from a mapping."""


class FromSequence[V](ABC):
    """Class that provides a method to generate a list of objects from a sequence."""

    @classmethod
    @abstractmethod
    def from_sequence[S](cls: Type[S], sequence: Sequence[V], /, **kwargs: Any) -> List[S]:
        """Generate a list of objects from a sequence."""
