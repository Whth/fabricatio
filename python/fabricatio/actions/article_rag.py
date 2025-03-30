"""A module for writing articles using RAG (Retrieval-Augmented Generation) capabilities."""

from asyncio import gather
from typing import Dict, Optional

from fabricatio.capabilities.rag import RAG
from fabricatio.models.action import Action
from fabricatio.models.extra.article_main import Article, ArticleParagraphSequencePatch, ArticleSubsection
from fabricatio.utils import ok


class TweakArticleRAG(Action, RAG):
    """Write an article based on the provided outline."""

    output_key: str = "rag_tweaked_article"

    async def _execute(
        self,
        article: Article,
        collection_name: str = "article_essence",
        citation_requirement: str = "Prioritize formulas from reference highlights."
        "Specify authors/years only."
        "You can create numeric citation numbers for article whose `bibtex_cite_key` is 'wangWind2024' by using notation like `#cite(<wangWind2024>)`."
        "Paragraphs must exceed 2-3 sentences",
        supervisor_check: bool = False,
        parallel: bool = False,
        **cxt,
    ) -> Optional[Article]:
        """Write an article based on the provided outline."""
        criteria = await self.draft_rating_criteria(topic := citation_requirement, criteria_count=8)

        tweak_manual = ok(await self.draft_rating_manual(topic, criteria=criteria))
        self.view(collection_name)

        if parallel:
            await gather(
                *[
                    self._inner(article, subsec, supervisor_check, citation_requirement, topic, tweak_manual)
                    for _, __, subsec in article.iter_subsections()
                ],
                return_exceptions=True,
            )
        else:
            for _, __, subsec in article.iter_subsections():
                await self._inner(article, subsec, supervisor_check, citation_requirement, topic, tweak_manual)
        return article

    async def _inner(
        self,
        article: Article,
        subsec: ArticleSubsection,
        supervisor_check: bool,
        citation_requirement: str,
        topic: str,
        tweak_manual: Dict[str, str],
    ) -> None:
        refind_q = ok(
            await self.arefined_query(
                f"{article.referenced.as_prompt()}\n"
                f"# Subsection requiring reference enhancement\n"
                f"{subsec.display()}\n"
                f"# Requirement\n"
                f"Search related articles in the base to find reference candidates, "
                f"prioritizing both original article language and English usage",
            )
        )
        patch = ArticleParagraphSequencePatch.default()
        patch.tweaked = subsec.paragraphs
        await self.correct_obj_inplace(
            patch,
            reference=f"{await self.aretrieve_compact(refind_q, final_limit=30)}\n{citation_requirement}",
            topic=topic,
            rating_manual=tweak_manual,
            supervisor_check=supervisor_check,
        )
