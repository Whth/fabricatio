"""A module for the RAG (Retrieval Augmented Generation) model."""

from operator import itemgetter
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Self, Union

from fabricatio.config import configs
from fabricatio.models.usages import LLMUsage
from fabricatio.models.utils import MilvusData
from more_itertools.recipes import flatten

try:
    from pymilvus import MilvusClient
except ImportError as e:
    raise RuntimeError("pymilvus is not installed. Have you installed `fabricatio[rag]` instead of `fabricatio`") from e
from pydantic import PrivateAttr


class Rag(LLMUsage):
    """A class representing the RAG (Retrieval Augmented Generation) model."""

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

    def view(self, collection_name: str, create: bool = False) -> Self:
        """View the specified collection.

        Args:
            collection_name (str): The name of the collection.
            create (bool): Whether to create the collection if it does not exist.
        """
        if create and self._client.has_collection(collection_name):
            self._client.create_collection(collection_name)

        self._target_collection = collection_name
        return self

    def quit_view(self) -> Self:
        """Quit the current view.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        self._target_collection = None
        return self

    @property
    def viewing_collection(self) -> Optional[str]:
        """Get the name of the collection being viewed.

        Returns:
            Optional[str]: The name of the collection being viewed.
        """
        return self._target_collection

    @property
    def safe_viewing_collection(self) -> str:
        """Get the name of the collection being viewed, raise an error if not viewing any collection.

        Returns:
            str: The name of the collection being viewed.
        """
        if self._target_collection is None:
            raise RuntimeError("No collection is being viewed. Have you called `self.view()`?")
        return self._target_collection

    def add_document[D: Union[Dict[str, Any], MilvusData]](
        self, data: D | List[D], collection_name: Optional[str] = None
    ) -> Self:
        """Adds a document to the specified collection.

        Args:
            data (Union[Dict[str, Any], MilvusData] | List[Union[Dict[str, Any], MilvusData]]): The data to be added to the collection.
            collection_name (Optional[str]): The name of the collection. If not provided, the currently viewed collection is used.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        if isinstance(data, MilvusData):
            data = data.prepare_insertion()
        if isinstance(data, list):
            data = [d.prepare_insertion() if isinstance(d, MilvusData) else d for d in data]
        self._client.insert(collection_name or self.safe_viewing_collection, data)
        return self

    def consume(
        self, source: PathLike, reader: Callable[[PathLike], MilvusData], collection_name: Optional[str] = None
    ) -> Self:
        """Consume a file and add its content to the collection.

        Args:
            source (PathLike): The path to the file to be consumed.
            reader (Callable[[PathLike], MilvusData]): The reader function to read the file.
            collection_name (Optional[str]): The name of the collection. If not provided, the currently viewed collection is used.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        data = reader(Path(source))
        self.add_document(data, collection_name or self.safe_viewing_collection)
        return self

    async def afetch_document(
        self,
        vecs: List[List[float]],
        desired_fields: List[str] | str,
        collection_name: Optional[str] = None,
        result_per_query: int = 10,
    ) -> List[Dict[str, Any]] | List[Any]:
        """Fetch data from the collection.

        Args:
            vecs (List[List[float]]): The vectors to search for.
            desired_fields (List[str] | str): The fields to retrieve.
            collection_name (Optional[str]): The name of the collection. If not provided, the currently viewed collection is used.
            result_per_query (int): The number of results to return per query.

        Returns:
            List[Dict[str, Any]] | List[Any]: The retrieved data.
        """
        # Step 1: Search for vectors
        search_results = self._client.search(
            collection_name or self.safe_viewing_collection,
            vecs,
            output_fields=desired_fields if isinstance(desired_fields, list) else [desired_fields],
            limit=result_per_query,
        )

        # Step 2: Flatten the search results
        flattened_results = flatten(search_results)

        # Step 3: Sort by distance (descending)
        sorted_results = sorted(flattened_results, key=itemgetter("distance"), reverse=True)

        # Step 4: Extract the entities
        resp = [result["entity"] for result in sorted_results]

        if isinstance(desired_fields, list):
            return resp
        return [r.get(desired_fields) for r in resp]

    async def aretrieve(
        self,
        query: List[str] | str,
        collection_name: Optional[str] = None,
        result_per_query: int = 10,
        final_limit: int = 20,
    ) -> List[str]:
        """Retrieve data from the collection.

        Args:
            query (List[str] | str): The query to be used for retrieval.
            collection_name (Optional[str]): The name of the collection. If not provided, the currently viewed collection is used.
            result_per_query (int): The number of results to be returned per query.
            final_limit (int): The final limit on the number of results to return.

        Returns:
            List[str]: A list of strings containing the retrieved data.
        """
        if isinstance(query, str):
            query = [query]
        return await self.afetch_document(
            vecs=(await self.vectorize(query)),
            desired_fields="text",
            collection_name=collection_name,
            result_per_query=result_per_query,
        )[:final_limit]
