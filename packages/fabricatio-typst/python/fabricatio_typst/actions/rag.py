"""The retrieval side of the article pipeline: write from the reference corpus, and build it.

The stage at the top is the RAG variant of the content phase — every subsection is
written against references retrieved from the article-essence table, and the citations
land inline; the actions below it build and maintain that table from the run's own
documents.
"""

from fabricatio_core.utils import cfg

cfg(["lancedb"])

from asyncio import gather
from pathlib import Path

from fabricatio_core.models.action import Action
from fabricatio_core.utils import ok
from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbFetchRAGConfig, LancedbRAG
from fabricatio_lancedb.config import lancedb_config
from fabricatio_rag.actions.db import StoreDocuments
from fabricatio_rule.capabilities.censor import Censor
from fabricatio_rule.models.rule import RuleSet

from fabricatio_typst.actions.article import ComposeSubsectionsStage
from fabricatio_typst.capabilities.rag import CitationSubsectionCompose
from fabricatio_typst.models.article_main import Article, ArticleSubsection
from fabricatio_typst.models.article_rag import ArticleChunk, ArticleEssenceStorable
from fabricatio_typst.models.context.subsection import SubsectionContext
from fabricatio_typst.rust import BibManager

__all__ = ["ChunkArticle", "RagComposeSubsectionsStage", "StoreArticleEssence", "TweakArticleLancedbRAG"]


class RagComposeSubsectionsStage(ComposeSubsectionsStage, CitationSubsectionCompose[SubsectionContext]):
    """Write every subsection against the reference corpus, then close each section and chapter out.

    The RAG variant of the content stage: the walk and the closing hooks are the plain
    stage's, while each subsection's write retrieves its own references first and lands
    them as inline citations.
    """


class TweakArticleLancedbRAG(
    Action,
    LancedbRAG[ArticleEssenceStorable, LancedbAddRAGConfig, LancedbFetchRAGConfig[ArticleEssenceStorable]],
    Censor,
):
    """Write an article based on the provided outline.

    This class inherits from `Action`, `RAG`, and `Censor` to provide capabilities for writing and refining articles
    using Retrieval-Augmented Generation (RAG) techniques. It processes an article outline, enhances subsections by
    searching for related references, and applies censoring rules to ensure compliance with the provided ruleset.
    """

    output_key: str = "rag_tweaked_article"
    """The key used to store the output of the action."""

    ruleset: RuleSet | None = None
    """The ruleset to be used for censoring the article."""

    ref_limit: int = 30
    """The limit of references to be retrieved"""

    async def _execute(
        self,
        article: Article,
        table_name: str = lancedb_config.default_table_name,
        twk_rag_ruleset: RuleSet | None = None,
        parallel: bool = False,
        **cxt,
    ) -> Article:
        """Write an article based on the provided outline.

        This method processes the article outline, either in parallel or sequentially, by enhancing each subsection
        with relevant references and applying censoring rules.

        Args:
            article (Article): The article to be processed.
            table_name (str): The LanceDB table holding the reference corpus; defaults to the configured table.
            twk_rag_ruleset (Optional[RuleSet]): The ruleset to apply for censoring. If not provided, the class's ruleset is used.
            parallel (bool): If True, process subsections in parallel. Otherwise, process them sequentially.
            **cxt: Additional context parameters.

        Returns:
            Article: The processed article with enhanced subsections and applied censoring rules.
        """
        if parallel:
            await gather(
                *[
                    self._inner(
                        article, subsec, ok(twk_rag_ruleset or self.ruleset, "No ruleset provided!"), table_name
                    )
                    for _, __, subsec in article.iter_subsections()
                ],
                return_exceptions=True,
            )
        else:
            for _, __, subsec in article.iter_subsections():
                await self._inner(
                    article, subsec, ok(twk_rag_ruleset or self.ruleset, "No ruleset provided!"), table_name
                )
        return article

    async def _inner(self, article: Article, subsec: ArticleSubsection, ruleset: RuleSet, table_name: str) -> None:
        """Enhance a subsection of the article with references and apply censoring rules.

        This method refines the query for the subsection, retrieves related references, and applies censoring rules
        to the subsection's paragraphs.

        Args:
            article (Article): The article containing the subsection.
            subsec (ArticleSubsection): The subsection to be enhanced.
            ruleset (RuleSet): The ruleset to apply for censoring.
            table_name (str): The LanceDB table to search for the references.

        Returns:
            None
        """
        refind_q = ok(
            await self.arefined_query(
                f"{article.artifacts.access_outline().as_prompt()}\n# Subsection requiring reference enhancement\n{subsec.display()}\n",
            ),
        )
        conf = LancedbFetchRAGConfig[ArticleEssenceStorable](
            document_model=ArticleEssenceStorable,
            limit=self.ref_limit,
            table_name=table_name,
        )
        refs = await self.afetch_document(refind_q, conf)
        await self.censor_obj_inplace(
            subsec,
            ruleset=ruleset,
            reference=f"{'\n\n'.join(d.display() for d in refs)}\n\n"
            f"You can use Reference above to rewrite the `{subsec.__class__.__name__}`.\n"
            f"You should Always use `{subsec.language}` as written language, "
            f"which is the original language of the `{subsec.title}`. "
            f"since rewrite a `{subsec.__class__.__name__}` in a different language is usually a bad choice",
        )


class ChunkArticle(Action):
    """Chunk an article into smaller chunks."""

    output_key: str = "article_chunks"
    """The key used to store the output of the action."""
    max_chunk_size: int | None = None
    """The maximum size of each chunk."""
    max_overlapping_rate: float | None = None
    """The maximum overlapping rate between chunks."""

    async def _execute(
        self,
        article_path: str | Path,
        bib_manager: BibManager,
        max_chunk_size: int | None = None,
        max_overlapping_rate: float | None = None,
        **_,
    ) -> list[ArticleChunk]:
        return ArticleChunk.from_file(
            article_path,
            bib_manager,
            max_chunk_size=ok(max_chunk_size or self.max_chunk_size, "No max_chunk_size provided!"),
            max_overlapping_rate=ok(
                max_overlapping_rate or self.max_overlapping_rate,
                "No max_overlapping_rate provided!",
            ),
        )


class StoreArticleEssence(
    StoreDocuments[
        ArticleEssenceStorable,
        ArticleEssenceStorable,
        LancedbAddRAGConfig,
        LancedbFetchRAGConfig[ArticleEssenceStorable],
    ],
    LancedbRAG[ArticleEssenceStorable, LancedbAddRAGConfig, LancedbFetchRAGConfig[ArticleEssenceStorable]],
):
    """Store ArticleEssence instances into LanceDB."""
