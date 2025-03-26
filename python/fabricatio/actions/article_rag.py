"""A module for writing articles using RAG (Retrieval-Augmented Generation) capabilities."""

from asyncio import gather
from typing import Dict, Optional

from fabricatio.capabilities.rag import RAG
from fabricatio.models.action import Action
from fabricatio.models.extra.article_main import Article, ArticleParagraphPatch, ArticleSubsection
from fabricatio.models.utils import ok


class TweakArticleRAG(Action, RAG):
    """Write an article based on the provided outline."""

    output_key: str = "rag_tweaked_article"

    async def _execute(
        self,
        article: Article,
        collection_name: str = "article_essence",
        citation_requirement: str = "# Citation Format\n"
        "Use correct citation format based on author count. Cite using author surnames and year:"
        "For 3+ authors: 'Author1, Author2 et al. (YYYY)'"
        "For 2 authors: 'Author1 & Author2 (YYYY)'"
        "Single author: 'Author1 (YYYY)'"
        "Multiple citations: 'Author1 (YYYY), Author2 (YYYY)'"
        "Prioritize formulas from reference highlights."
        "Specify authors/years only - no numeric citations"
        "Paragraphs must exceed 2-3 sentences",
        supervisor_check: bool = False,
        parallel: bool = False,
        **cxt,
    ) -> Optional[Article]:
        """Write an article based on the provided outline."""
        criteria = await self.draft_rating_criteria(
            topic := "choose appropriate reference to insert into the article, "
            "making conclusions or reasoning based on concrete evidence instead of unreliable guesses."
            "Extensively use formulas highlighted in reference文献 should be translated to 'references'."
            "Only specify authors and years without numeric citation numbers (like [1],[2])."
            "Each paragraph should not end with just 2-3 sentences for better readability.",
            criteria_count=13,
        )

        tweak_manual = ok(
            await self.draft_rating_manual(topic, criteria=criteria, co_extractor={"model": "openai/qwen-max"})
        )
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
        patch = ArticleParagraphPatch.default()
        patch.tweaked = subsec.paragraphs
        await self.correct_obj_inplace(
            patch,
            reference=f"{await self.aretrieve_compact(refind_q, final_limit=50)}\n{citation_requirement}",
            topic=topic,
            rating_manual=tweak_manual,
            supervisor_check=supervisor_check,
        )
