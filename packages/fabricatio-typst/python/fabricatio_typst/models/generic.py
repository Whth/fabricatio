from abc import ABC, abstractmethod

from fabricatio_core.models.generic import Base


class ModelHash(Base, ABC):
    """Class that provides a hash value for the object.

    This class includes a method to calculate a hash value for the object based on its JSON representation.
    """

    def __hash__(self) -> int:
        """Calculates a hash value for the object based on its model_dump_json representation.

        Returns:
            int: The hash value of the object.
        """
        return hash(self.model_dump_json())


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
