"""A module for writing articles using RAG (Retrieval-Augmented Generation) capabilities."""

from asyncio import gather
from pathlib import Path
from typing import List, Optional

from fabricatio import BibManager
from fabricatio.capabilities.censor import Censor
from fabricatio.capabilities.extract import Extract
from fabricatio.capabilities.rag import RAG
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra.aricle_rag import ArticleChunk, CitationManager
from fabricatio.models.extra.article_essence import ArticleEssence
from fabricatio.models.extra.article_main import Article, ArticleChapter, ArticleSection, ArticleSubsection
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.models.extra.rule import RuleSet
from fabricatio.utils import ok


class WriteArticleContentRAG(Action, RAG, Extract):
    """Write an article based on the provided outline."""

    ref_limit: int = 35
    """The limit of references to be retrieved"""
    extractor_model: str
    """The model to use for extracting the content from the retrieved references."""
    query_model: str
    """The model to use for querying the database"""

    req: str = (
        "citation number is REQUIRED to cite any reference!\n"
        "Everything is build upon the typst language, which is similar to latex, \n"
        "Legal citing syntax examples(seperated by |): [[1]]|[[1,2]]|[[1-3]]|[[12,13-15]]|[[1-3,5-7]]\n"
        "Illegal citing syntax examples(seperated by |): [[1],[2],[3]]|[[1],[1-2]]\n"
        "Those reference mark shall not be omitted during the extraction\n"
        "It's recommended to cite multiple references that supports your conclusion at a time.\n"
        "Wrapp inline expression using $ $, and wrapp block equation using $$ $$."
        "In addition to that, you can add a label outside the block equation which can be used as a cross reference identifier, the label is a string wrapped in `<` and `>`,"
        "you can refer to that label by using the syntax with prefix of `@eqt:`"
        "Below is a usage example:\n"
        "```typst\n"
        "See @eqt:mass-energy-equation , it's the equation.\n"
        "$$\n"
        "E = m c^2"
        "$$\n"
        "<mass-energy-equation>"
        "In @eqt:mass-energy-equation , we get the foundation of physics.\n"
        "```"
    )

    async def _execute(
        self,
        article_outline: ArticleOutline,
        writing_ruleset: RuleSet,
        collection_name: str = "article_chunks",
        **cxt,
    ) -> Article:
        article = Article.from_outline(article_outline).update_ref(article_outline)
        await gather(
            *[
                self._inner(article, article_outline, chap, sec, subsec)
                for chap, sec, subsec in article.iter_subsections()
            ]
        )
        return article.convert_tex()

    async def _inner(
        self,
        article: Article,
        article_outline: ArticleOutline,
        chap: ArticleChapter,
        sec: ArticleSection,
        subsec: ArticleSubsection,
    ) -> ArticleSubsection:
        ref_q = ok(
            await self.arefined_query(
                f"{article_outline.display()}\n\nAbove is my article outline, I m writing graduate thesis titled `{article.title}`. "
                f"More specifically, i m witting the Chapter `{chap.title}` >> Section `{sec.title}` >> Subsection `{subsec.title}`.\n"
                f"I need to search related references to build up the content of the subsec mentioned above, which is `{subsec.title}`.\n"
                f"plus, you can search required formulas by using latex equation code.\n"
                f"provide 10 queries as possible, to get best result!\n"
                f"You should provide both English version and chinese version of the refined queries!\n",
                model=self.query_model,
            ),
            "Failed to refine query.",
        )
        ret = await self.aretrieve(ref_q, ArticleChunk, final_limit=self.ref_limit, result_per_query=6)
        ret.reverse()
        cm = CitationManager().update_chunks(ret)

        raw_paras = await self.aask(
            f"{cm.as_prompt()}\nAbove is some related reference retrieved for you."
            f"{article.referenced.display()}\n\nAbove is my article outline, I m writing graduate thesis titled `{article.title}`. "
            f"More specifically, i m witting the Chapter `{chap.title}` >> Section `{sec.title}` >> Subsection `{subsec.title}`.\n"
            f"Please help me write the paragraphs of the subsec mentioned above, which is `{subsec.title}`.\n"
            f"{self.req}\n"
            f"You SHALL use `{article.language}` as writing language."
        )

        raw_paras = (
            raw_paras.replace(r" \( ", "$").replace(r" \) ", "$").replace("\\[\n", "$$\n").replace("\n\\]", "\n$$")
        )

        new_subsec = ok(
            await self.extract(
                ArticleSubsection,
                raw_paras,
                f"Above is the subsection titled `{subsec.title}`.\n"
                f"I need you to extract the content to update my subsection obj provided below.\n{self.req}"
                f"{subsec.display()}\n",
            ),
            "Failed to propose new subsection.",
        )

        for p in new_subsec.paragraphs:
            p.content = cm.apply(p.content).replace("$$", "\n$$\n")

        subsec.update_from(new_subsec)
        logger.debug(f"{subsec.title}:rpl\n{subsec.display()}")
        return subsec


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

    ref_limit: int = 30
    """The limit of references to be retrieved"""

    async def _execute(
        self,
        article: Article,
        collection_name: str = "article_essence",
        twk_rag_ruleset: Optional[RuleSet] = None,
        parallel: bool = False,
        **cxt,
    ) -> Article:
        """Write an article based on the provided outline.

        This method processes the article outline, either in parallel or sequentially, by enhancing each subsection
        with relevant references and applying censoring rules.

        Args:
            article (Article): The article to be processed.
            collection_name (str): The name of the collection to view for processing.
            twk_rag_ruleset (Optional[RuleSet]): The ruleset to apply for censoring. If not provided, the class's ruleset is used.
            parallel (bool): If True, process subsections in parallel. Otherwise, process them sequentially.
            **cxt: Additional context parameters.

        Returns:
            Article: The processed article with enhanced subsections and applied censoring rules.
        """
        self.view(collection_name)

        if parallel:
            await gather(
                *[
                    self._inner(article, subsec, ok(twk_rag_ruleset or self.ruleset, "No ruleset provided!"))
                    for _, __, subsec in article.iter_subsections()
                ],
                return_exceptions=True,
            )
        else:
            for _, __, subsec in article.iter_subsections():
                await self._inner(article, subsec, ok(twk_rag_ruleset or self.ruleset, "No ruleset provided!"))
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
                f"{article.referenced.as_prompt()}\n# Subsection requiring reference enhancement\n{subsec.display()}\n"
            )
        )
        await self.censor_obj_inplace(
            subsec,
            ruleset=ruleset,
            reference=f"{'\n\n'.join(d.display() for d in await self.aretrieve(refind_q, document_model=ArticleEssence, final_limit=self.ref_limit))}\n\n"
            f"You can use Reference above to rewrite the `{subsec.__class__.__name__}`.\n"
            f"You should Always use `{subsec.language}` as written language, "
            f"which is the original language of the `{subsec.title}`. "
            f"since rewrite a `{subsec.__class__.__name__}` in a different language is usually a bad choice",
        )


class ChunkArticle(Action):
    """Chunk an article into smaller chunks."""

    output_key: str = "article_chunks"
    """The key used to store the output of the action."""
    max_chunk_size: Optional[int] = None
    """The maximum size of each chunk."""
    max_overlapping_rate: Optional[float] = None
    """The maximum overlapping rate between chunks."""

    async def _execute(
        self,
        article_path: str | Path,
        bib_manager: BibManager,
        max_chunk_size: Optional[int] = None,
        max_overlapping_rate: Optional[float] = None,
        **_,
    ) -> List[ArticleChunk]:
        return ArticleChunk.from_file(
            article_path,
            bib_manager,
            max_chunk_size=ok(max_chunk_size or self.max_chunk_size, "No max_chunk_size provided!"),
            max_overlapping_rate=ok(
                max_overlapping_rate or self.max_overlapping_rate, "No max_overlapping_rate provided!"
            ),
        )
