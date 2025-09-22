"""base classes for all research components."""

from abc import ABC, abstractmethod
from typing import Optional, Union, overload

from fabricatio_core.models.generic import Base
from fabricatio_core.utils import ok
from pydantic import PrivateAttr


class WithRef[T](Base, ABC):
    """Class that provides a reference to another object.

    This class manages a reference to another object, allowing for easy access and updates.
    """

    _reference: Optional[T] = PrivateAttr(None)

    @property
    def referenced(self) -> T:
        """Get the referenced object.

        Returns:
            T: The referenced object.

        Raises:
            ValueError: If the reference is not set.
        """
        return ok(
            self._reference, f"`{self.__class__.__name__}`'s `_reference` field is None. Have you called `update_ref`?"
        )

    @overload
    def update_ref[S: WithRef](self: S, reference: T) -> S: ...

    @overload
    def update_ref[S: WithRef](self: S, reference: "WithRef[T]") -> S: ...

    @overload
    def update_ref[S: WithRef](self: S, reference: None = None) -> S: ...

    def update_ref[S: WithRef](self: S, reference: Union[T, "WithRef[T]", None] = None) -> S:
        """Update the reference of the object.

        Args:
            reference (Union[T, WithRef[T], None]): The new reference to set.

        Returns:
            S: The current instance with the updated reference.
        """
        if isinstance(reference, self.__class__):
            self._reference = reference.referenced
        else:
            self._reference = reference  # pyright: ignore [reportAttributeAccessIssue]
        return self


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
