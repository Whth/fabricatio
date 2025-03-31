"""A module for the RAG (Retrieval Augmented Generation) model."""

try:
    from pymilvus import MilvusClient
except ImportError as e:
    raise RuntimeError("pymilvus is not installed. Have you installed `fabricatio[rag]` instead of `fabricatio`?") from e
from functools import lru_cache
from operator import itemgetter
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Self, Union, Unpack, cast, overload

from more_itertools.recipes import flatten, unique
from pydantic import Field, PrivateAttr

from fabricatio.config import configs
from fabricatio.journal import logger
from fabricatio.models.kwargs_types import (
    ChooseKwargs,
    CollectionConfigKwargs,
    EmbeddingKwargs,
    FetchKwargs,
    LLMKwargs,
    RetrievalKwargs,
)
from fabricatio.models.usages import EmbeddingUsage
from fabricatio.models.utils import MilvusData
from fabricatio.rust_instances import TEMPLATE_MANAGER
from fabricatio.utils import ok


@lru_cache(maxsize=None)
def create_client(uri: str, token: str = "", timeout: Optional[float] = None) -> MilvusClient:
    """Create a Milvus client."""
    return MilvusClient(
        uri=uri,
        token=token,
        timeout=timeout,
    )


class RAG(EmbeddingUsage):
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
            uri=milvus_uri or ok(self.milvus_uri or configs.rag.milvus_uri).unicode_string(),
            token=milvus_token
            or (token.get_secret_value() if (token := (self.milvus_token or configs.rag.milvus_token)) else ""),
            timeout=milvus_timeout or self.milvus_timeout or configs.rag.milvus_timeout,
        )
        return self

    def check_client(self, init: bool = True) -> Self:
        """Check if the client is initialized, and if not, initialize it."""
        if self._client is None and init:
            return self.init_client()
        if self._client is None and not init:
            raise RuntimeError("Client is not initialized. Have you called `self.init_client()`?")
        return self

    @overload
    async def pack(
        self, input_text: List[str], subject: Optional[str] = None, **kwargs: Unpack[EmbeddingKwargs]
    ) -> List[MilvusData]: ...
    @overload
    async def pack(
        self, input_text: str, subject: Optional[str] = None, **kwargs: Unpack[EmbeddingKwargs]
    ) -> MilvusData: ...

    async def pack(
        self, input_text: List[str] | str, subject: Optional[str] = None, **kwargs: Unpack[EmbeddingKwargs]
    ) -> List[MilvusData] | MilvusData:
        """Asynchronously generates MilvusData objects for the given input text.

        Args:
            input_text (List[str] | str): A string or list of strings to generate embeddings for.
            subject (Optional[str]): The subject of the input text. Defaults to None.
            **kwargs (Unpack[EmbeddingKwargs]): Additional keyword arguments for embedding.

        Returns:
            List[MilvusData] | MilvusData: The generated MilvusData objects.
        """
        if isinstance(input_text, str):
            return MilvusData(vector=await self.vectorize(input_text, **kwargs), text=input_text, subject=subject)
        vecs = await self.vectorize(input_text, **kwargs)
        return [
            MilvusData(
                vector=vec,
                text=text,
                subject=subject,
            )
            for text, vec in zip(input_text, vecs, strict=True)
        ]

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
                or configs.rag.milvus_dimensions
                or self.embedding_dimensions
                or configs.embedding.dimensions,
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
        if self.target_collection is None:
            raise RuntimeError("No collection is being viewed. Have you called `self.view()`?")
        return self.target_collection

    def add_document[D: Union[Dict[str, Any], MilvusData]](
        self, data: D | List[D], collection_name: Optional[str] = None, flush: bool = False
    ) -> Self:
        """Adds a document to the specified collection.

        Args:
            data (Union[Dict[str, Any], MilvusData] | List[Union[Dict[str, Any], MilvusData]]): The data to be added to the collection.
            collection_name (Optional[str]): The name of the collection. If not provided, the currently viewed collection is used.
            flush (bool): Whether to flush the collection after insertion.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        if isinstance(data, MilvusData):
            prepared_data = data.prepare_insertion()
        elif isinstance(data, list):
            prepared_data = [d.prepare_insertion() if isinstance(d, MilvusData) else d for d in data]
        else:
            raise TypeError(f"Expected MilvusData or list of MilvusData, got {type(data)}")
        c_name = collection_name or self.safe_target_collection
        self.check_client().client.insert(c_name, prepared_data)

        if flush:
            logger.debug(f"Flushing collection {c_name}")
            self.client.flush(c_name)
        return self

    async def consume_file(
        self,
        source: List[PathLike] | PathLike,
        reader: Callable[[PathLike], str] = lambda path: Path(path).read_text(encoding="utf-8"),
        collection_name: Optional[str] = None,
    ) -> Self:
        """Consume a file and add its content to the collection.

        Args:
            source (PathLike): The path to the file to be consumed.
            reader (Callable[[PathLike], MilvusData]): The reader function to read the file.
            collection_name (Optional[str]): The name of the collection. If not provided, the currently viewed collection is used.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        if not isinstance(source, list):
            source = [source]
        return await self.consume_string([reader(s) for s in source], collection_name)

    async def consume_string(self, text: List[str] | str, collection_name: Optional[str] = None) -> Self:
        """Consume a string and add it to the collection.

        Args:
            text (List[str] | str): The text to be added to the collection.
            collection_name (Optional[str]): The name of the collection. If not provided, the currently viewed collection is used.

        Returns:
            Self: The current instance, allowing for method chaining.
        """
        self.add_document(await self.pack(text), collection_name or self.safe_target_collection, flush=True)
        return self

    @overload
    async def afetch_document[V: (int, str, float, bytes)](
        self,
        vecs: List[List[float]],
        desired_fields: List[str],
        collection_name: Optional[str] = None,
        similarity_threshold: float = 0.37,
        result_per_query: int = 10,
    ) -> List[Dict[str, V]]: ...

    @overload
    async def afetch_document[V: (int, str, float, bytes)](
        self,
        vecs: List[List[float]],
        desired_fields: str,
        collection_name: Optional[str] = None,
        similarity_threshold: float = 0.37,
        result_per_query: int = 10,
    ) -> List[V]: ...
    async def afetch_document[V: (int, str, float, bytes)](
        self,
        vecs: List[List[float]],
        desired_fields: List[str] | str,
        collection_name: Optional[str] = None,
        similarity_threshold: float = 0.37,
        result_per_query: int = 10,
    ) -> List[Dict[str, Any]] | List[V]:
        """Fetch data from the collection.

        Args:
            vecs (List[List[float]]): The vectors to search for.
            desired_fields (List[str] | str): The fields to retrieve.
            collection_name (Optional[str]): The name of the collection. If not provided, the currently viewed collection is used.
            similarity_threshold (float): The threshold for similarity, only results above this threshold will be returned.
            result_per_query (int): The number of results to return per query.

        Returns:
            List[Dict[str, Any]] | List[Any]: The retrieved data.
        """
        # Step 1: Search for vectors
        search_results = self.check_client().client.search(
            collection_name or self.safe_target_collection,
            vecs,
            search_params={"radius": similarity_threshold},
            output_fields=desired_fields if isinstance(desired_fields, list) else [desired_fields],
            limit=result_per_query,
        )

        # Step 2: Flatten the search results
        flattened_results = flatten(search_results)
        unique_results = unique(flattened_results, key=itemgetter("id"))
        # Step 3: Sort by distance (descending)
        sorted_results = sorted(unique_results, key=itemgetter("distance"), reverse=True)

        logger.debug(f"Searched similarities: {[t['distance'] for t in sorted_results]}")
        # Step 4: Extract the entities
        resp = [result["entity"] for result in sorted_results]

        if isinstance(desired_fields, list):
            return resp
        return [r.get(desired_fields) for r in resp]  # extract the single field as list

    async def aretrieve(
        self,
        query: List[str] | str,
        final_limit: int = 20,
        **kwargs: Unpack[FetchKwargs],
    ) -> List[str]:
        """Retrieve data from the collection.

        Args:
            query (List[str] | str): The query to be used for retrieval.
            final_limit (int): The final limit on the number of results to return.
            **kwargs (Unpack[FetchKwargs]): Additional keyword arguments for retrieval.

        Returns:
            List[str]: A list of strings containing the retrieved data.
        """
        if isinstance(query, str):
            query = [query]
        return cast(
            "List[str]",
            await self.afetch_document(
                vecs=(await self.vectorize(query)),
                desired_fields="text",
                **kwargs,
            ),
        )[:final_limit]

    async def aretrieve_compact(
        self,
        query: List[str] | str,
        **kwargs: Unpack[RetrievalKwargs],
    ) -> str:
        """Retrieve data from the collection and format it for display.

        Args:
            query (List[str] | str): The query to be used for retrieval.
            **kwargs (Unpack[RetrievalKwargs]): Additional keyword arguments for retrieval.

        Returns:
            str: A formatted string containing the retrieved data.
        """
        return TEMPLATE_MANAGER.render_template(
            configs.templates.retrieved_display_template, {"docs": (await self.aretrieve(query, **kwargs))}
        )

    async def aask_retrieved(
        self,
        question: str,
        query: Optional[List[str] | str] = None,
        collection_name: Optional[str] = None,
        extra_system_message: str = "",
        result_per_query: int = 10,
        final_limit: int = 20,
        similarity_threshold: float = 0.37,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Asks a question by retrieving relevant documents based on the provided query.

        This method performs document retrieval using the given query, then asks the
        specified question using the retrieved documents as context.

        Args:
            question (str): The question to be asked.
            query (List[str] | str): The query or list of queries used for document retrieval.
            collection_name (Optional[str]): The name of the collection to retrieve documents from.
                                              If not provided, the currently viewed collection is used.
            extra_system_message (str): An additional system message to be included in the prompt.
            result_per_query (int): The number of results to return per query. Default is 10.
            final_limit (int): The maximum number of retrieved documents to consider. Default is 20.
            similarity_threshold (float): The threshold for similarity, only results above this threshold will be returned.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments passed to the underlying `aask` method.

        Returns:
            str: A string response generated after asking with the context of retrieved documents.
        """
        rendered = await self.aretrieve_compact(
            query or question,
            final_limit=final_limit,
            collection_name=collection_name,
            result_per_query=result_per_query,
            similarity_threshold=similarity_threshold,
        )

        logger.debug(f"Retrieved Documents: \n{rendered}")
        return await self.aask(
            question,
            f"{rendered}\n\n{extra_system_message}",
            **kwargs,
        )

    async def arefined_query(self, question: List[str] | str, **kwargs: Unpack[ChooseKwargs]) -> Optional[List[str]]:
        """Refines the given question using a template.

        Args:
            question (List[str] | str): The question to be refined.
            **kwargs (Unpack[ChooseKwargs]): Additional keyword arguments for the refinement process.

        Returns:
            List[str]: A list of refined questions.
        """
        return await self.alist_str(
            TEMPLATE_MANAGER.render_template(
                configs.templates.refined_query_template,
                {"question": [question] if isinstance(question, str) else question},
            ),
            **kwargs,
        )

    async def aask_refined(
        self,
        question: str,
        collection_name: Optional[str] = None,
        extra_system_message: str = "",
        result_per_query: int = 10,
        final_limit: int = 20,
        similarity_threshold: float = 0.37,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Asks a question using a refined query based on the provided question.

        Args:
            question (str): The question to be asked.
            collection_name (Optional[str]): The name of the collection to retrieve documents from.
            extra_system_message (str): An additional system message to be included in the prompt.
            result_per_query (int): The number of results to return per query. Default is 10.
            final_limit (int): The maximum number of retrieved documents to consider. Default is 20.
            similarity_threshold (float): The threshold for similarity, only results above this threshold will be returned.
            **kwargs (Unpack[LLMKwargs]): Additional keyword arguments passed to the underlying `aask` method.

        Returns:
            str: A string response generated after asking with the refined question.
        """
        return await self.aask_retrieved(
            question,
            await self.arefined_query(question, **kwargs),
            collection_name=collection_name,
            extra_system_message=extra_system_message,
            result_per_query=result_per_query,
            final_limit=final_limit,
            similarity_threshold=similarity_threshold,
            **kwargs,
        )
