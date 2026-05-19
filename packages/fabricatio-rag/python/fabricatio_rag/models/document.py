"""Base class for document models."""

from abc import ABCMeta, abstractmethod
from typing import Self, Sequence

from fabricatio_capabilities.models.generic import AsPrompt
from fabricatio_core.models.generic import Base, Vectorizable


class StoredDocumentModel[ST](Vectorizable, Base, metaclass=ABCMeta):
    """A base class for document models."""

    @abstractmethod
    def prepare_insertion(self, vector: Sequence[float]) -> ST:
        """Prepares the data for insertion into a vector database."""


class SearchedDocumentModel[SD](AsPrompt, Base, metaclass=ABCMeta):
    """A base class for document models retrieved from a vector database."""

    @classmethod
    @abstractmethod
    def from_raw(cls, raw: SD) -> Self:
        """Create the searched model from the rawdata searched from the db."""
