"""Base class for document models."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Self, Sequence


class DocumentModel(ABC):
    """A base class for document models."""

    @classmethod
    @abstractmethod
    def from_sequence(cls, data: Sequence[dict]) -> List[Self]:
        """Constructs a list of instances from a sequence of dictionaries."""

    @abstractmethod
    def prepare_vectorization(self) -> str:
        """Prepares the data for vectorization."""

    @abstractmethod
    def prepare_insertion(self, vector: Sequence[float]) -> Dict[str, Any]:
        """Prepares the data for insertion into a vector database."""
