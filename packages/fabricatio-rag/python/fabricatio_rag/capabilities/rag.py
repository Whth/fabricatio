"""A module for the RAG (Retrieval Augmented Generation) model."""

from abc import ABC, abstractmethod
from typing import List, Optional, Self, Type, Unpack

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.usages import UseEmbedding, UseLLM, UseReranker
from fabricatio_core.models.generic import Base
from fabricatio_core.models.kwargs_types import ListStringKwargs, RerankerKwargs

from fabricatio_rag.config import rag_config
from fabricatio_rag.models.document import DocumentModel


class RAGConfigBase(Base):
    """A base class for RAG (Retrieval Augmented Generation) configuration."""

    @classmethod
    def default(cls) -> Self:
        return cls()


class RAG[D: DocumentModel, AC: RAGConfigBase, FC: RAGConfigBase](UseEmbedding, UseReranker, UseLLM, ABC):
    """A class representing the RAG (Retrieval Augmented Generation) model."""

    @abstractmethod
    async def add_document(
        self,
        data: D | List[D],
        config: AC | None = None,
    ) -> Self:
        """Add documents to a collection."""
        pass

    @abstractmethod
    async def afetch_document(
        self,
        query: str | List[str],
        document_model: Type[D],
        config: FC | None = None,
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

    async def arank_documents(
        self,
        query: str,
        documents: List[D],
        **kwargs: Unpack[RerankerKwargs],
    ) -> List[D]:
        """Rerank documents by relevance to query, preserving document objects.

        Delegates to UseReranker.arank() for scoring, then reorders the
        original document list by descending score.

        Args:
            query: The query text to rank against.
            documents: Previously retrieved documents to rerank.
            **kwargs: Additional keyword arguments for the reranking process.

        Returns:
            Documents reordered by relevance (descending score).
        """
        if not documents:
            return []
        rankings = await self.arank(query=query, documents=[doc.prepare_vectorization() for doc in documents], **kwargs)
        return [documents[idx] for idx, _ in rankings]
