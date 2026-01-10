from typing import List, Literal, Self, Tuple

class TEIClient:
    """Client for TEI reranking service.

    Handles communication with a TEI reranking service to reorder text snippets
    based on their relevance to a query.
    """

    async def connect(self, base_url: str) -> Self:
        """Connect to TEI reranking service."""

    async def arerank(
        self,
        query: str,
        texts: List[str],
        truncate: bool = False,
        truncation_direction: Literal["Left", "Right"] = "Left",
    ) -> List[Tuple[int, float]]:
        """Rerank texts based on relevance to query.

        Args:
            query: The query to match texts against
            texts: List of text snippets to rerank
            truncate: Whether to truncate texts to fit model context
            truncation_direction: Direction to truncate from ("Left" or "Right")

        Returns:
            List of tuples containing (original_index, relevance_score)

        Raises:
            RuntimeError: If reranking fails or truncation_direction is invalid
        """

    async def embed_all(
        self,
        text: str,
        truncate: bool = False,
        truncation_direction: Literal["Left", "Right"] = "Left",
    ) -> List[List[float]]:
        """Generate embeddings for all tokens in the text.

        Args:
            text: The input text to generate embeddings for
            truncate: Whether to truncate texts to fit model context
            truncation_direction: Direction to truncate from ("Left" or "Right")

        Returns:
            List of lists containing token embeddings

        Raises:
            RuntimeError: If embedding generation fails or truncation_direction is invalid
        """

    async def embed(
        self,
        text: str,
        dimensions: int | None = None,
        truncate: bool = False,
        truncation_direction: Literal["Left", "Right"] = "Left",
    ) -> List[float]:
        """Generate embeddings for the given text.

        Args:
            text: The input text to generate embeddings for
            dimensions: Optional parameter to specify the number of dimensions in the output embeddings
            truncate: Whether to truncate texts to fit model context
            truncation_direction: Direction to truncate from ("Left" or "Right")

        Returns:
            List of floats representing the embeddings

        Raises:
            RuntimeError: If embedding generation fails or truncation_direction is invalid
        """
