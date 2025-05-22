"""base classes for all research components."""

from abc import ABC, abstractmethod

from fabricatio_core.models.generic import Base


class Introspect(ABC):
    """Class that provides a method to introspect the object.

    This class includes a method to perform internal introspection of the object.
    """

    @abstractmethod
    def introspect(self) -> str:
        """Internal introspection of the object.

        Returns:
            str: The internal introspection of the object.
        """


class WordCount(Base, ABC):
    """Class that includes a word count attribute."""

    expected_word_count: int
    """Expected word count of this research component."""

    @property
    def exact_word_count(self) -> int:
        """Get the exact word count of this research component."""
        raise NotImplementedError(f"`exact_word_count` is not implemented for {self.__class__.__name__}")
