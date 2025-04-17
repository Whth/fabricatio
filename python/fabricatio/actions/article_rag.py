"""A module for writing articles using RAG (Retrieval-Augmented Generation) capabilities."""

from asyncio import gather
from pathlib import Path
from typing import List, Optional

from pydantic import PositiveInt

from fabricatio import BibManager
from fabricatio.capabilities.censor import Censor
from fabricatio.capabilities.extract import Extract
from fabricatio.capabilities.rag import RAG
from fabricatio.decorators import precheck_package
from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.extra.aricle_rag import ArticleChunk, CitationManager
from fabricatio.models.extra.article_essence import ArticleEssence
from fabricatio.models.extra.article_main import Article, ArticleChapter, ArticleSection, ArticleSubsection
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.models.extra.rule import RuleSet
from fabricatio.utils import ask_retain, ok

TYPST_CITE_USAGE = (
    "citation number is REQUIRED to cite any reference!,for example in Auther Pattern: 'Doe et al.[[1]], Jack et al.[[2]]' or in Sentence Suffix Sattern: 'Global requirement is incresing[[1]].'\n"
    "Everything is build upon the typst language, which is similar to latex, \n"
    "Legal citing syntax examples(seperated by |): [[1]]|[[1,2]]|[[1-3]]|[[12,13-15]]|[[1-3,5-7]]\n"
    "Illegal citing syntax examples(seperated by |): [[1],[2],[3]]|[[1],[1-2]]\n"
    "Those reference mark shall not be omitted during the extraction\n"
    "It's recommended to cite multiple references that supports your conclusion at a time.\n"
    "Wrapp inline expression using $ $,like '$>5m$' '$89%$' , and wrapp block equation using $$ $$. if you are using '$' as the money unit, you should add a '\\' before it to avoid being interpreted as a inline equation. For example 'The pants worths 5\\$.'\n"
    "In addition to that, you can add a label outside the block equation which can be used as a cross reference identifier, the label is a string wrapped in `<` and `>` like `<energy-release-rate-equation>`.Note that the label string should be a summarizing title for the equation being labeled.\n"
    "you can refer to that label by using the syntax with prefix of `@eqt:`, which indicate that this notation is citing a label from the equations. For example ' @eqt:energy-release-rate-equation ' DO remember that the notation shall have both suffixed and prefixed space char which enable the compiler to distinguish the notation from the plaintext."
    "Below is a usage example:\n"
    "```typst\n"
    "See @eqt:mass-energy-equation , it's the foundation of physics.\n"
    "$$\n"
    "E = m c^2\n"
    "$$  <mass-energy-equation>\n\n\n"
    "In @eqt:mass-energy-equation , $m$ stands for mass, $c$ stands for speed of light, and $E$ stands for energy. \n"
    "```"
)


class WriteArticleContentRAG(Action, RAG, Extract):
    """Write an article based on the provided outline."""

    ref_limit: int = 35
    """The limit of references to be retrieved"""
    threshold: float = 0.62
    """The threshold of relevance"""
    extractor_model: str
    """The model to use for extracting the content from the retrieved references."""
    query_model: str
    """The model to use for querying the database"""
    supervisor: bool = False
    """Whether to use supervisor mode"""
    result_per_query: PositiveInt = 4
    """The number of results to be returned per query."""
    req: str = TYPST_CITE_USAGE
    """The req of the write article content."""

    async def _execute(
        self,
        article_outline: ArticleOutline,
        collection_name: Optional[str] = None,
        supervisor: Optional[bool] = None,
        **cxt,
    ) -> Article:
        article = Article.from_outline(article_outline).update_ref(article_outline)
        self.target_collection = collection_name or self.safe_target_collection
        if supervisor or (supervisor is None and self.supervisor):
            for chap, sec, subsec in article.iter_subsections():
                await self._supervisor_inner(article, article_outline, chap, sec, subsec)

        else:
            await gather(
                *[
                    self._inner(article, article_outline, chap, sec, subsec)
                    for chap, sec, subsec in article.iter_subsections()
                ]
            )
        return article.convert_tex()

    @precheck_package(
        "questionary", "`questionary` is required for supervisor mode, please install it by `fabricatio[qa]`"
    )
    async def _supervisor_inner(
        self,
        article: Article,
        article_outline: ArticleOutline,
        chap: ArticleChapter,
        sec: ArticleSection,
        subsec: ArticleSubsection,
    ) -> ArticleSubsection:
        from questionary import confirm, text
        from rich import print as r_print

        cm = CitationManager()
        await self.search_database(article, article_outline, chap, sec, subsec, cm)

        raw = await self.write_raw(article, article_outline, chap, sec, subsec, cm)
        r_print(raw)

        while not await confirm("Accept this version and continue?").ask_async():
            if inst := await text("Search for more refs for additional spec.").ask_async():
                await self.search_database(
                    article,
                    article_outline,
                    chap,
                    sec,
                    subsec,
                    cm,
                    supervisor=True,
                    extra_instruction=inst,
                )

            if instruction := await text("Enter the instructions to improve").ask_async():
                raw = await self.write_raw(article, article_outline, chap, sec, subsec, cm, instruction)
            if edt := await text("Edit", default=raw).ask_async():
                raw = edt

            r_print(raw)

        return await self.extract_new_subsec(subsec, raw, cm)

    async def _inner(
        self,
        article: Article,
        article_outline: ArticleOutline,
        chap: ArticleChapter,
        sec: ArticleSection,
        subsec: ArticleSubsection,
    ) -> ArticleSubsection:
        cm = CitationManager()

        await self.search_database(article, article_outline, chap, sec, subsec, cm)

        raw_paras = await self.write_raw(article, article_outline, chap, sec, subsec, cm)

        raw_paras = "\n".join(p for p in raw_paras.splitlines() if p and not p.endswith("**") and not p.startswith("#"))

        return await self.extract_new_subsec(subsec, raw_paras, cm)

    async def extract_new_subsec(
        self, subsec: ArticleSubsection, raw_paras: str, cm: CitationManager
    ) -> ArticleSubsection:
        """Extract the new subsec."""
        new_subsec = ok(
            await self.extract(
                ArticleSubsection,
                raw_paras,
                f"Above is the subsection titled `{subsec.title}`.\n"
                f"I need you to extract the content to update my subsection obj provided below.\n{self.req}"
                f"{subsec.display()}\n",
                model=self.extractor_model,
            ),
            "Failed to propose new subsection.",
        )
        for p in new_subsec.paragraphs:
            p.content = cm.apply(p.content).replace("$$", "\n$$\n")
        subsec.update_from(new_subsec)
        logger.debug(f"{subsec.title}:rpl\n{subsec.display()}")
        return subsec

    async def write_raw(
        self,
        article: Article,
        article_outline: ArticleOutline,
        chap: ArticleChapter,
        sec: ArticleSection,
        subsec: ArticleSubsection,
        cm: CitationManager,
        extra_instruction: str = "",
    ) -> str:
        """Write the raw paragraphs of the subsec."""
        return (
            (
                await self.aask(
                    f"{cm.as_prompt()}\nAbove is some related reference from other auther retrieved for you."
                    f"{article_outline.finalized_dump()}\n\nAbove is my article outline, I m writing graduate thesis titled `{article.title}`. "
                    f"More specifically, i m witting the Chapter `{chap.title}` >> Section `{sec.title}` >> Subsection `{subsec.title}`.\n"
                    f"Please help me write the paragraphs of the subsec mentioned above, which is `{subsec.title}`.\n"
                    f"{self.req}\n"
                    f"You SHALL use `{article.language}` as writing language.\n{extra_instruction}\n"
                    f"Do not use numbered list to display the outcome, you should regard you are writing the main text of the thesis.\n"
                    f"You should not copy others' works from the references directly on to my thesis, we can only harness the conclusion they have drawn.\n"
                    f"No extra explanation is allowed."
                )
            )
            .replace(r" \( ", "$")
            .replace(r" \) ", "$")
            .replace(r"\(", "$")
            .replace(r"\)", "$")
            .replace("\\[\n", "$$\n")
            .replace("\\[ ", "$$\n")
            .replace("\n\\]", "\n$$")
            .replace(" \\]", "\n$$")
        )

    async def search_database(
        self,
        article: Article,
        article_outline: ArticleOutline,
        chap: ArticleChapter,
        sec: ArticleSection,
        subsec: ArticleSubsection,
        cm: CitationManager,
        extra_instruction: str = "",
        supervisor: bool = False,
    ) -> None:
        """Search database for related references."""
        search_req = (
            f"{article_outline.finalized_dump()}\n\nAbove is my article outline, I m writing graduate thesis titled `{article.title}`. "
            f"More specifically, i m witting the Chapter `{chap.title}` >> Section `{sec.title}` >> Subsection `{subsec.title}`.\n"
            f"I need to search related references to build up the content of the subsec mentioned above, which is `{subsec.title}`.\n"
            f"provide 10~16 queries as possible, to get best result!\n"
            f"You should provide both English version and chinese version of the refined queries!\n{extra_instruction}\n"
        )

        ref_q = ok(
            await self.arefined_query(
                search_req,
                model=self.query_model,
            ),
            "Failed to refine query.",
        )

        if supervisor:
            ref_q = await ask_retain(ref_q)
        ret = await self.aretrieve(
            ref_q,
            ArticleChunk,
            final_limit=self.ref_limit,
            result_per_query=self.result_per_query,
            similarity_threshold=self.threshold,
        )

        cm.add_chunks(ok(ret))
        ref_q = await self.arefined_query(
            f"{cm.as_prompt()}\n\nAbove is the retrieved references in the first RAG, now we need to perform the second RAG.\n\n{search_req}",
            model=self.query_model,
        )

        if ref_q is None:
            logger.warning("Second refine query is None, skipping.")
            return
        if supervisor:
            ref_q = await ask_retain(ref_q)

        ret = await self.aretrieve(
            ref_q,
            ArticleChunk,
            final_limit=self.ref_limit,
            result_per_query=self.result_per_query,
            similarity_threshold=self.threshold,
        )
        if ret is None:
            logger.warning("Second retrieve is None, skipping.")
            return
        cm.add_chunks(ret)


class ArticleConsultRAG(Action, RAG):
    """Write an article based on the provided outline."""

    output_key: str = "consult_count"

    ref_limit: int = 20
    """The final limit of references."""
    ref_per_q: int = 3
    """The limit of references to retrieve per query."""
    similarity_threshold: float = 0.62
    """The similarity threshold of references to retrieve."""
    ref_q_model: Optional[str] = None
    """The model to use for refining query."""
    req: str = TYPST_CITE_USAGE
    """The request for the rag model."""

    @precheck_package(
        "questionary", "`questionary` is required for supervisor mode, please install it by `fabricatio[qa]`"
    )
    async def _execute(self, collection_name: Optional[str] = None, **cxt) -> int:
        from questionary import confirm, text
        from rich import print as r_print

        from fabricatio.rust import convert_all_block_tex, convert_all_inline_tex

        self.target_collection = collection_name or self.safe_target_collection

        cm = CitationManager()

        counter = 0
        while (req := await text("User: ").ask_async()) is not None:
            if await confirm("Empty the cm?").ask_async():
                cm.empty()
            ref_q = await self.arefined_query(req, model=self.ref_q_model)
            refs = await self.aretrieve(
                ok(ref_q, "Failed to refine query."),
                ArticleChunk,
                final_limit=self.ref_limit,
                result_per_query=self.ref_per_q,
                similarity_threshold=self.similarity_threshold,
            )

            ret = await self.aask(f"{cm.add_chunks(refs).as_prompt()}\n{self.req}\n{req}")
            ret = convert_all_inline_tex(ret)
            ret = convert_all_block_tex(ret)
            ret = cm.apply(ret)

            r_print(ret)
            counter += 1
        logger.info(f"{counter} rounds of conversation.")
        return counter


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
