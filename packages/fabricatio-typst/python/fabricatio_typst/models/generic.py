"""base classes for all research components."""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Union, final, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import Base
from fabricatio_core.utils import ok
from pydantic import PrivateAttr

from fabricatio_typst.config import typst_config


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


class AsPrompt:
    """Class that provides a method to generate a prompt from the model.

    This class includes a method to generate a prompt based on the model's attributes.
    """

    @final
    def as_prompt(self) -> str:
        """Generate a prompt from the model.

        Returns:
            str: The generated prompt.
        """
        return TEMPLATE_MANAGER.render_template(
            typst_config.as_prompt_template,
            self._as_prompt_inner(),
        )

    @abstractmethod
    def _as_prompt_inner(self) -> Dict[str, str]:
        """Generate the inner part of the prompt.

        This method should be implemented by subclasses to provide the specific data for the prompt.

        Returns:
            Dict[str, str]: The data for the prompt.
        """


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
