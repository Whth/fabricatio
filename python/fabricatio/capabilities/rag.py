"""A module for the RAG (Retrieval Augmented Generation) model."""

from typing import Any, Dict, List, Optional, Self, Union

from fabricatio.config import configs
from fabricatio.models.utils import MilvusData

try:
    from pymilvus import MilvusClient
except ImportError as e:
    raise RuntimeError("pymilvus is not installed. Have you installed `fabricatio[rag]` instead of `fabricatio`") from e
from pydantic import BaseModel, ConfigDict, PrivateAttr


class Rag(BaseModel):
    """A class representing the RAG (Retrieval Augmented Generation) model."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    _client: MilvusClient = PrivateAttr(
        default=MilvusClient(
            uri=configs.rag.milvus_uri.unicode_string(),
            token=configs.rag.milvus_token.get_secret_value(),
            timeout=configs.rag.milvus_timeout,
        ),
    )
    _target_collection: Optional[str] = PrivateAttr(default=None)

    @property
    def client(self) -> MilvusClient:
        """The Milvus client."""
        return self._client

    def add_document[D: Union[Dict[str, Any] | MilvusData]](self, collection_name: str, data: D | List[D]) -> Self:
        """Adds a document to the specified collection.

        Args:
            collection_name (str): The name of the collection.
            data (dict): The data to be added to the collection.
        """
        if isinstance(data, MilvusData):
            data = data.prepare_insertion()
        if isinstance(data, list):
            data = [d.prepare_insertion() if isinstance(d, MilvusData) else d for d in data]
        self.client.insert(collection_name, data)
        return self
