"""base classes for all research components."""

from abc import ABC, abstractmethod


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
