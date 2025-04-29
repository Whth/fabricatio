"""A collection of utility functions for the fabricatio package."""

from typing import Any, Dict, List, Mapping, Optional, TypedDict, Unpack, overload

import aiohttp
import requests

from fabricatio.decorators import precheck_package
from fabricatio.journal import logger
from fabricatio.models.kwargs_types import RerankOptions


@precheck_package(
    "questionary", "'questionary' is required to run this function. Have you installed `fabricatio[qa]`?."
)
async def ask_edit(text_seq: List[str]) -> List[str]:
    """Asks the user to edit a list of texts.

    Args:
        text_seq (List[str]): A list of texts to be edited.

    Returns:
        List[str]: A list of edited texts.
        If the user does not edit a text, it will not be included in the returned list.
    """
    from questionary import text

    res = []
    for i, t in enumerate(text_seq):
        edited = await text(f"[{i}] ", default=t).ask_async()
        if edited:
            res.append(edited)
    return res


@overload
async def ask_retain[V](candidates: List[str]) -> List[str]: ...


@overload
async def ask_retain[V](candidates: List[str], value_mapping: List[V]) -> List[V]: ...


@precheck_package(
    "questionary", "'questionary' is required to run this function. Have you installed `fabricatio[qa]`?."
)
async def ask_retain[V](candidates: List[str], value_mapping: Optional[List[V]] = None) -> List[str] | List[V]:
    """Asks the user to retain a list of candidates."""
    from questionary import Choice, checkbox

    return await checkbox(
        "Please choose those that should be retained.",
        choices=[Choice(p, value=p, checked=True) for p in candidates]
        if value_mapping is None
        else [Choice(p, value=v, checked=True) for p, v in zip(candidates, value_mapping, strict=True)],
    ).ask_async()


def override_kwargs(kwargs: Mapping[str, Any], **overrides) -> Dict[str, Any]:
    """Override the values in kwargs with the provided overrides."""
    new_kwargs = dict(kwargs.items())
    new_kwargs.update(overrides)
    return new_kwargs


def fallback_kwargs(kwargs: Mapping[str, Any], **fallbacks) -> Dict[str, Any]:
    """Fallback the values in kwargs with the provided fallbacks."""
    new_kwargs = dict(kwargs.items())
    new_kwargs.update({k: v for k, v in fallbacks.items() if k not in new_kwargs})
    return new_kwargs


def ok[T](val: Optional[T], msg: str = "Value is None") -> T:
    """Check if a value is None and raise a ValueError with the provided message if it is.

    Args:
        val: The value to check.
        msg: The message to include in the ValueError if val is None.

    Returns:
        T: The value if it is not None.
    """
    if val is None:
        raise ValueError(msg)
    return val


def wrapp_in_block(string: str, title: str, style: str = "-") -> str:
    """Wraps a string in a block with a title.

    Args:
        string: The string to wrap.
        title: The title of the block.
        style: The style of the block.

    Returns:
        str: The wrapped string.
    """
    return f"--- Start of {title} ---\n{string}\n--- End of {title} ---".replace("-", style)


class RerankResult(TypedDict):
    """The rerank result."""

    index: int
    score: float


class RerankerAPI:
    """A class to interact with the /rerank API for text reranking."""

    def __init__(self, base_url: str) -> None:
        """Initialize the RerankerAPI instance.

        Args:
            base_url (str): The base URL of the TEI-deployed reranker model API.
                Example: "http://localhost:8000".
        """
        self.base_url = base_url.rstrip("/")  # Ensure no trailing slashes

    @staticmethod
    def _map_error_code(status_code: int, error_data: Dict[str, str]) -> Exception:
        """Map HTTP status codes and error data to specific exceptions.

        Args:
            status_code (int): The HTTP status code returned by the API.
            error_data (Dict[str, str]): The error details returned by the API.

        Returns:
            Exception: A specific exception based on the error code and message.
        """
        error_message = error_data.get("error", "Unknown error")

        if status_code == 400:
            return ValueError(f"Bad request: {error_message}")
        if status_code == 413:
            return ValueError(f"Batch size error: {error_message}")
        if status_code == 422:
            return RuntimeError(f"Tokenization error: {error_message}")
        if status_code == 424:
            return RuntimeError(f"Rerank error: {error_message}")
        if status_code == 429:
            return RuntimeError(f"Model overloaded: {error_message}")
        return RuntimeError(f"Unexpected error ({status_code}): {error_message}")

    def rerank(self, query: str, texts: List[str], **kwargs: Unpack[RerankOptions]) -> List[RerankResult]:
        """Call the /rerank API to rerank a list of texts based on a query (synchronous).

        Args:
            query (str): The query string used for matching with the texts.
            texts (List[str]): A list of texts to be reranked.
            **kwargs (Unpack[RerankOptions]): Optional keyword arguments:
                - raw_scores (bool, optional): Whether to return raw scores. Defaults to False.
                - truncate (bool, optional): Whether to truncate the texts. Defaults to False.
                - truncation_direction (Literal["left", "right"], optional): Direction of truncation. Defaults to "right".

        Returns:
            List[RerankResult]: A list of dictionaries containing the reranked results.
                Each dictionary includes:
                - "index" (int): The original index of the text.
                - "score" (float): The relevance score.

        Raises:
            ValueError: If input parameters are invalid or the API returns a client-side error.
            RuntimeError: If the API call fails or returns a server-side error.
        """
        # Validate inputs
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")
        if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
            raise ValueError("Texts must be a list of strings.")

        # Construct the request payload
        payload = {
            "query": query,
            "texts": texts,
            **kwargs,
        }

        try:
            # Send POST request to the API
            response = requests.post(f"{self.base_url}/rerank", json=payload)

            # Handle non-200 status codes
            if not response.ok:
                error_data = None
                if "application/json" in response.headers.get("Content-Type", ""):
                    error_data = response.json()
                else:
                    error_data = {"error": response.text, "error_type": "unexpected_mimetype"}
                raise self._map_error_code(response.status_code, error_data)

            # Parse the JSON response
            data: List[RerankResult] = response.json()
            logger.debug(f"Rerank for `{query}` get {[s['score'] for s in data]}")
            return data

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to connect to the API: {e}") from e

    async def arerank(self, query: str, texts: List[str], **kwargs: Unpack[RerankOptions]) -> List[RerankResult]:
        """Call the /rerank API to rerank a list of texts based on a query (asynchronous).

        Args:
            query (str): The query string used for matching with the texts.
            texts (List[str]): A list of texts to be reranked.
            **kwargs (Unpack[RerankOptions]): Optional keyword arguments:
                - raw_scores (bool, optional): Whether to return raw scores. Defaults to False.
                - truncate (bool, optional): Whether to truncate the texts. Defaults to False.
                - truncation_direction (Literal["left", "right"], optional): Direction of truncation. Defaults to "right".

        Returns:
            List[RerankResult]: A list of dictionaries containing the reranked results.
                Each dictionary includes:
                - "index" (int): The original index of the text.
                - "score" (float): The relevance score.

        Raises:
            ValueError: If input parameters are invalid or the API returns a client-side error.
            RuntimeError: If the API call fails or returns a server-side error.
        """
        # Validate inputs
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")
        if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
            raise ValueError("Texts must be a list of strings.")

        # Construct the request payload
        payload = {
            "query": query,
            "texts": texts,
            **kwargs,
        }

        try:
            # Send POST request to the API using aiohttp
            async with (
                aiohttp.ClientSession() as session,
                session.post(f"{self.base_url}/rerank", json=payload) as response,
            ):
                # Handle non-200 status codes
                if not response.ok:
                    if "application/json" in response.headers.get("Content-Type", ""):
                        error_data = await response.json()
                    else:
                        error_data = {"error": await response.text(), "error_type": "unexpected_mimetype"}
                    raise self._map_error_code(response.status, error_data)

                # Parse the JSON response
                data: List[RerankResult] = await response.json()
                logger.debug(f"Rerank for `{query}` get {[s['score'] for s in data]}")
                return data

        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to connect to the API: {e}") from e
