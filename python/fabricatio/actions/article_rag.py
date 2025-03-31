"""A module for writing articles using RAG (Retrieval-Augmented Generation) capabilities."""

from asyncio import gather
from typing import Optional

from fabricatio.capabilities.censor import Censor
from fabricatio.capabilities.rag import RAG
from fabricatio.models.action import Action
from fabricatio.models.extra.article_main import Article, ArticleParagraphSequencePatch, ArticleSubsection
from fabricatio.models.extra.rule import RuleSet
from fabricatio.utils import ok


class TweakArticleRAG(Action, RAG, Censor):
    """Write an article based on the provided outline.

    This class inherits from `Action`, `RAG`, and `Censor` to provide capabilities for writing and refining articles
    using Retrieval-Augmented Generation (RAG) techniques. It processes an article outline, enhances subsections by
    searching for related references, and applies censoring rules to ensure compliance with the provided ruleset.

    Attributes:
        output_key (str): The key used to store the output of the action.
        ruleset (Optional[RuleSet]): The ruleset to be used for censoring the article.
    """

    output_key: str = "rag_tweaked_article"
    """The key used to store the output of the action."""

    ruleset: Optional[RuleSet] = None
    """The ruleset to be used for censoring the article."""

    async def _execute(
        self,
        article: Article,
        collection_name: str = "article_essence",
        ruleset: Optional[RuleSet] = None,
        parallel: bool = False,
        **cxt,
    ) -> Optional[Article]:
        """Write an article based on the provided outline.

        This method processes the article outline, either in parallel or sequentially, by enhancing each subsection
        with relevant references and applying censoring rules.

        Args:
            article (Article): The article to be processed.
            collection_name (str): The name of the collection to view for processing.
            ruleset (Optional[RuleSet]): The ruleset to apply for censoring. If not provided, the class's ruleset is used.
            parallel (bool): If True, process subsections in parallel. Otherwise, process them sequentially.
            **cxt: Additional context parameters.

        Returns:
            Optional[Article]: The processed article with enhanced subsections and applied censoring rules.
        """
        self.view(collection_name)

        if parallel:
            await gather(
                *[
                    self._inner(article, subsec, ok(ruleset or self.ruleset, "No ruleset provided!"))
                    for _, __, subsec in article.iter_subsections()
                ],
                return_exceptions=True,
            )
        else:
            for _, __, subsec in article.iter_subsections():
                await self._inner(article, subsec, ok(ruleset or self.ruleset, "No ruleset provided!"))
        return article

    async def _inner(self, article: Article, subsec: ArticleSubsection, ruleset: RuleSet) -> None:
        """Enhance a subsection of the article with references and apply censoring rules.

        This method refines the query for the subsection, retrieves related references, and applies censoring rules
        to the subsection's paragraphs.

        Args:
            article (Article): The article containing the subsection.
            subsec (ArticleSubsection): The subsection to be enhanced.
            ruleset (RuleSet): The ruleset to apply for censoring.

        Returns:
            None
        """
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
        await self.censor_obj_inplace(
            patch,
            ruleset=ruleset,
            reference=await self.aretrieve_compact(refind_q, final_limit=30),
        )
