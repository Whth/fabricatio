"""A module for writing articles using RAG (Retrieval-Augmented Generation) capabilities."""

from typing import Optional

from fabricatio.capabilities.rag import RAG
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra.article_main import Article
from fabricatio.models.extra.article_outline import ArticleOutline


class GenerateArticleRAG(Action, RAG):
    """Write an article based on the provided outline."""

    output_key: str = "article"

    async def _execute(self, article_outline: ArticleOutline, **cxt) -> Optional[Article]:
        """Write an article based on the provided outline."""
        logger.info(f"Writing an article based on the outline:\n{article_outline.title}")
        refined_q = await self.arefined_query(article_outline.display())
        return await self.propose(
            Article,
            article_outline.display(),
            **self.prepend_sys_msg(f"{await self.aretrieve_compact(refined_q)}\n{self.briefing}"),
        )


class WriteArticleFineGrind(Action, RAG):
    """Fine-grind an article based on the provided outline."""

    output_key: str = "article"

    async def _execute(self, article_outline: ArticleOutline, **cxt) -> Optional[Article]:
        """Fine-grind an article based on the provided outline."""
        logger.info(f"Fine-grinding an article based on the outline:\n{article_outline.title}")
