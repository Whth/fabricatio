"""A module for the RAG (Retrieval Augmented Generation) model."""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Self, Type, Union, Unpack

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.usages import UseEmbedding
from fabricatio_core.models.kwargs_types import ListStringKwargs

from fabricatio_rag.config import rag_config
from fabricatio_rag.models.document import DocumentModel


class RAG[D: DocumentModel](UseEmbedding, ABC):
    """A class representing the RAG (Retrieval Augmented Generation) model."""

    @abstractmethod
    async def add_document(
        self,
        data: Any,
        **kwargs: Any,
    ) -> Self:
        """Add documents to a collection."""
        pass

    @abstractmethod
    async def afetch_document(
        self,
        query: Union[str, List[str]],
        document_model: Type[D],
        **kwargs: Any,
    ) -> List[D]:
        """Fetch documents based on query."""
        pass

    async def arefined_query(
        self,
        question: List[str] | str,
        **kwargs: Unpack[ListStringKwargs],
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
