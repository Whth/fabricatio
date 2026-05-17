"""Base class for document models."""

from abc import abstractmethod
from typing import Sequence

from fabricatio_core.models.generic import Vectorizable


class DocumentModel[ST](Vectorizable):
    """A base class for document models."""

    @abstractmethod
    def prepare_insertion(self, vector: Sequence[float]) -> ST:
        """Prepares the data for insertion into a vector database."""
