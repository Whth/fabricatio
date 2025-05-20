from typing import List, Tuple, Literal


class TEIClient:
    """Client for TEI reranking service.

    Handles communication with a TEI reranking service to reorder text snippets
    based on their relevance to a query.
    """

    def __init__(self, base_url: str) -> None:
        """Initialize the TEI client.

        Args:
            base_url: URL to the TEI reranking service
        """

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
