"""This module contains the capabilities for the milvus."""

from functools import cache
from operator import itemgetter
from typing import List, Optional, Self, Type, Unpack

from fabricatio_core import logger
from fabricatio_core.utils import ok
from fabricatio_rag.capabilities.rag import RAG, RAGConfigBase
from more_itertools import flatten, unique
from pydantic import Field, PrivateAttr
from pymilvus import MilvusClient

from fabricatio_milvus.config import milvus_config
from fabricatio_milvus.models.kwargs_types import CollectionConfigKwargs
from fabricatio_milvus.models.milvus import MilvusDataBase, MilvusScopedConfig


@cache
def create_client(uri: str, token: str = "", timeout: Optional[float] = None) -> MilvusClient:
    """Create a Milvus client."""
    return MilvusClient(
        uri=uri,
        token=token,
        timeout=timeout,
    )


class AddConfig(RAGConfigBase):
    """Configuration for adding documents to a Milvus collection."""

    flush: bool = False
    collection_name: Optional[str] = None


class FetchConfig(RAGConfigBase):
    """Configuration for fetching documents from a Milvus collection."""

    collection_name: Optional[str] = None
    similarity_threshold: float = 0.37
    result_per_query: int = 10
    tei_endpoint: Optional[str] = None
    reranker_threshold: float = 0.7
    filter_expr: str = ""


class MilvusRAG[D: MilvusDataBase, AC: AddConfig, FC: FetchConfig](MilvusScopedConfig, RAG[D, AC, FC]):
    """A class for the RAG model using Milvus."""

    target_collection: Optional[str] = Field(default=None)
    """The name of the collection being viewed."""

    _client: Optional[MilvusClient] = PrivateAttr(None)
    """The Milvus client used for the RAG model."""

    @property
    def client(self) -> MilvusClient:
        """Return the Milvus client."""
        return ok(self._client, "Client is not initialized. Have you called `self.init_client()`?")

    def init_client(
        self,
        milvus_uri: Optional[str] = None,
        milvus_token: Optional[str] = None,
        milvus_timeout: Optional[float] = None,
    ) -> Self:
        """Initialize the Milvus client."""
        self._client = create_client(
            uri=milvus_uri or ok(self.milvus_uri or milvus_config.milvus_uri),
            token=milvus_token
            or (token.get_secret_value() if (token := (self.milvus_token or milvus_config.milvus_token)) else ""),
            timeout=milvus_timeout or self.milvus_timeout or milvus_config.milvus_timeout,
        )
        return self

    def check_client(self, init: bool = True) -> Self:
        """Check if the client is initialized, and if not, initialize it."""
        if self._client is None and init:
            return self.init_client()
        if self._client is None and not init:
            raise RuntimeError("Client is not initialized. Have you called `self.init_client()`?")
        return self

    def view(
        self, collection_name: Optional[str], create: bool = False, **kwargs: Unpack[CollectionConfigKwargs]
    ) -> Self:
        """View the specified collection.

        Args:
            collection_name (str): The name of the collection.
            create (bool): Whether to create the collection if it does not exist.
            **kwargs (Unpack[CollectionConfigKwargs]): Additional keyword arguments for collection configuration.
        """
        if create and collection_name and not self.check_client().client.has_collection(collection_name):
            kwargs["dimension"] = ok(
                kwargs.get("dimension") or self.milvus_dimensions or milvus_config.milvus_dimensions,
                "`dimension` is not set at any level.",
            )
            self.client.create_collection(collection_name, auto_id=True, **kwargs)
            logger.info(f"Creating collection {collection_name}")

        self.target_collection = collection_name
        return self

    def quit_viewing(self) -> Self:
        """Quit the current view.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        return self.view(None)

    @property
    def safe_target_collection(self) -> str:
        """Get the name of the collection being viewed, raise an error if not viewing any collection.

        Returns:
            str: The name of the collection being viewed.
        """
        return ok(self.target_collection, "No collection is being viewed. Have you called `self.view()`?")

    async def add_document(
        self,
        data: D | List[D],
        config: AC | None = None,
    ) -> Self:
        """Adds a document to the specified collection.

        Args:
            data (D | List[D]): The data to be added to the collection.
            config (AC | None): Configuration for the add operation.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        config = config or AddConfig.default()

        data_seq = [data] if not isinstance(data, list) else data
        data_vec = await self.vectorize([d.prepare_vectorization() for d in data_seq])
        prepared_data = [d.prepare_insertion(vec) for d, vec in zip(data_seq, data_vec, strict=True)]

        c_name = config.collection_name or self.safe_target_collection
        self.check_client().client.insert(c_name, prepared_data)

        if config.flush:
            logger.debug(f"Flushing collection {c_name}")
            self.client.flush(c_name)
        return self

    async def afetcah_document(
        self,
        query: str | List[str],
        document_model: Type[D],
        config: FC | None = None,
    ) -> List[D]:
        """Asynchronously fetches documents from a Milvus database based on input vectors.

        Args:
           query (str | List[str]): A list of vectors to search for in the database.
           document_model (Type[D]): The model class used to convert fetched data into document objects.
           config (FC | None): Configuration for the fetch operation.

        Returns:
           List[D]: A list of document objects created from the fetched data.
        """
        config = config or FetchConfig.default()

        # Step 1: Search for vectors
        search_results = self.check_client().client.search(
            config.collection_name or self.safe_target_collection,
            await self.vectorize(query),
            search_params={"radius": config.similarity_threshold},
            output_fields=list(document_model.model_fields),
            filter=config.filter_expr,
            limit=config.result_per_query,
        )

        # Step 2: Flatten the search results
        flattened_results = flatten(search_results)
        unique_results = unique(flattened_results, key=itemgetter("id"))

        # Step 3: Sort by distance (descending)
        sorted_results = sorted(unique_results, key=itemgetter("distance"), reverse=True)

        logger.debug(
            f"Fetched {len(sorted_results)} document,searched similarities: {[t['distance'] for t in sorted_results]}"
        )
        # Step 4: Extract the entities
        resp = [result["entity"] for result in sorted_results]

        return document_model.from_sequence(resp)
