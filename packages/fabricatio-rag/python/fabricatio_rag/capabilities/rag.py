"""A module for the RAG (Retrieval Augmented Generation) model."""

from abc import ABC

from fabricatio_rag.config import rag_config

try:
    from pymilvus import MilvusClient
except ImportError as e:
    raise RuntimeError(
        "pymilvus is not installed. Have you installed `fabricatio[rag]` instead of `fabricatio`?"
    ) from e
from functools import lru_cache
from operator import itemgetter
from typing import List, Optional, Self, Type, Unpack

from fabricatio_core.journal import logger
from fabricatio_core.models.kwargs_types import ChooseKwargs
from fabricatio_core.models.usages import EmbeddingUsage
from fabricatio_core.rust import CONFIG, TEMPLATE_MANAGER
from fabricatio_core.utils import ok
from more_itertools.recipes import flatten, unique
from pydantic import Field, PrivateAttr

from fabricatio_rag.models.kwargs_types import CollectionConfigKwargs, FetchKwargs
from fabricatio_rag.models.rag import MilvusDataBase, MilvusScopedConfig


@lru_cache(maxsize=None)
def create_client(uri: str, token: str = "", timeout: Optional[float] = None) -> MilvusClient:
    """Create a Milvus client."""
    return MilvusClient(
        uri=uri,
        token=token,
        timeout=timeout,
    )


class RAG(EmbeddingUsage, MilvusScopedConfig, ABC):
    """A class representing the RAG (Retrieval Augmented Generation) model."""

    target_collection: Optional[str] = Field(default=None)
    """The name of the collection being viewed."""

    _client: Optional[MilvusClient] = PrivateAttr(None)
    """The Milvus client used for the RAG model."""

    @property
    def client(self) -> MilvusClient:
        """Return the Milvus client."""
        if self._client is None:
            raise RuntimeError("Client is not initialized. Have you called `self.init_client()`?")
        return self._client

    def init_client(
        self,
        milvus_uri: Optional[str] = None,
        milvus_token: Optional[str] = None,
        milvus_timeout: Optional[float] = None,
    ) -> Self:
        """Initialize the Milvus client."""
        self._client = create_client(
            uri=milvus_uri or ok(self.milvus_uri or rag_config.milvus_uri),
            token=milvus_token
            or (token.get_secret_value() if (token := (self.milvus_token or rag_config.milvus_token)) else ""),
            timeout=milvus_timeout or self.milvus_timeout or rag_config.milvus_timeout,
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
                kwargs.get("dimension")
                or self.milvus_dimensions
                or rag_config.milvus_dimensions
                or self.embedding_dimensions
                or CONFIG.embedding.dimensions,
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

    async def add_document[D: MilvusDataBase](
        self, data: List[D] | D, collection_name: Optional[str] = None, flush: bool = False
    ) -> Self:
        """Adds a document to the specified collection.

        Args:
            data (Union[Dict[str, Any], MilvusDataBase] | List[Union[Dict[str, Any], MilvusDataBase]]): The data to be added to the collection.
            collection_name (Optional[str]): The name of the collection. If not provided, the currently viewed collection is used.
            flush (bool): Whether to flush the collection after insertion.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        if isinstance(data, MilvusDataBase):
            data = [data]

        data_vec = await self.vectorize([d.prepare_vectorization() for d in data])
        prepared_data = [d.prepare_insertion(vec) for d, vec in zip(data, data_vec, strict=True)]

        c_name = collection_name or self.safe_target_collection
        self.check_client().client.insert(c_name, prepared_data)

        if flush:
            logger.debug(f"Flushing collection {c_name}")
            self.client.flush(c_name)
        return self

    async def afetch_document[D: MilvusDataBase](
        self,
        query: List[str],
        document_model: Type[D],
        collection_name: Optional[str] = None,
        similarity_threshold: float = 0.37,
        result_per_query: int = 10,
        tei_endpoint: Optional[str] = None,
        reranker_threshold: float = 0.7,
        filter_expr: str = "",
    ) -> List[D]:
        """Asynchronously fetches documents from a Milvus database based on input vectors.

        Args:
           query (List[str]): A list of vectors to search for in the database.
           document_model (Type[D]): The model class used to convert fetched data into document objects.
           collection_name (Optional[str]): The name of the collection to search within.
                                             If None, the currently viewed collection is used.
           similarity_threshold (float): The similarity threshold for vector search. Defaults to 0.37.
           result_per_query (int): The maximum number of results to return per query. Defaults to 10.
           tei_endpoint (str): the endpoint of the TEI api.
           reranker_threshold (float): The threshold used to filtered low relativity document.
           filter_expr (str) : The filter expression used to filter out unwanted documents.

        Returns:
           List[D]: A list of document objects created from the fetched data.
        """
        # Step 1: Search for vectors
        search_results = self.check_client().client.search(
            collection_name or self.safe_target_collection,
            await self.vectorize(query),
            search_params={"radius": similarity_threshold},
            output_fields=list(document_model.model_fields),
            filter=filter_expr,
            limit=result_per_query,
        )
        if tei_endpoint is not None:
            from fabricatio_rag.rust import TEIClient

            reranker = TEIClient(base_url=tei_endpoint)

            retrieved_id = set()
            raw_result = []

            for q, g in zip(query, search_results, strict=True):
                models = document_model.from_sequence([res["entity"] for res in g if res["id"] not in retrieved_id])
                logger.debug(f"Retrived {len(g)} raw document, filtered out {len(models)}.")
                retrieved_id.update(res["id"] for res in g)
                if not models:
                    continue
                rank_scores = await reranker.arerank(
                    q, [m.prepare_vectorization() for m in models], truncate=True, truncation_direction="Left"
                )
                raw_result.extend((models[idx], scr) for (idx, scr) in rank_scores if scr > reranker_threshold)

            raw_result_sorted = sorted(raw_result, key=lambda x: x[1], reverse=True)
            return [r[0] for r in raw_result_sorted]

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

    async def aretrieve[D: MilvusDataBase](
        self,
        query: List[str] | str,
        document_model: Type[D],
        max_accepted: int = 20,
        **kwargs: Unpack[FetchKwargs],
    ) -> List[D]:
        """Retrieve data from the collection.

        Args:
            query (List[str] | str): The query to be used for retrieval.
            document_model (Type[D]): The model class used to convert retrieved data into document objects.
            max_accepted (int): The final limit on the number of results to return.
            **kwargs (Unpack[FetchKwargs]): Additional keyword arguments for retrieval.

        Returns:
            List[D]: A list of document objects created from the retrieved data.
        """
        if isinstance(query, str):
            query = [query]

        return (
            await self.afetch_document(
                query=query,
                document_model=document_model,
                **kwargs,
            )
        )[:max_accepted]

    async def arefined_query(
        self, question: List[str] | str, **kwargs: Unpack[ChooseKwargs[Optional[List[str]]]]
    ) -> Optional[List[str]]:
        """Refines the given question using a template.

        Args:
            question (List[str] | str): The question to be refined.
            **kwargs (Unpack[ChooseKwargs]): Additional keyword arguments for the refinement process.

        Returns:
            List[str]: A list of refined questions.
        """
        return await self.alist_str(
            TEMPLATE_MANAGER.render_template(
                rag_config.refined_query_template,
                {"question": [question] if isinstance(question, str) else question},
            ),
            **kwargs,
        )
