"""Novel RAG capabilities combining novel composition with retrieval-augmented generation."""

import asyncio
from abc import ABC
from typing import List, Optional, Unpack

from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import cfg

from fabricatio_novel.models.scripting import Scene

cfg(["lancedb"])
from fabricatio_character.models.character import CharacterCard  # noqa: I001
from fabricatio_core import logger
from fabricatio_novel.models.novel_rag import WritingStyleDocument, WritingStyleFetchConfig

from fabricatio_core.utils import ok
from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbRAG

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.plan import ChapterPlan


class NovelComposeRAG(
    LancedbRAG[WritingStyleDocument, LancedbAddRAGConfig, WritingStyleFetchConfig], NovelCompose, ABC
):
    """Novel composition capability extended with writing style RAG support."""

    async def _fetch_style_docs(
        self,
        query: str,
        config: WritingStyleFetchConfig,
        rerank_query: Optional[str] = None,
    ) -> List[WritingStyleDocument]:
        """Fetch writing style docs and optionally rerank against `rerank_query`.

        When `rerank_query` is provided and non-empty, the fetch limit is scaled
        by `rerank_scale_factor` to give the reranker more candidates, then
        results are reranked and sliced back to `config.limit`.
        """
        q = f"{query}\n\nNeed Some refined question to find QA docs related to the stuff above"

        if rerank_query:
            q += f"\nand below is the extra user constrain which is more prior to follow: \n{rerank_query}"

        queries = await self.arefined_query(q)

        if not queries:
            return []

        if rerank_query and rerank_query.strip():
            scaled_limit = int(config.limit * novel_config.rerank_scale_factor)
            scaled_config = config.model_copy(update={"limit": scaled_limit})
            docs = list(ok(await self.afetch_document(queries, scaled_config)))
            if not docs:
                return []
            docs = docs[:scaled_limit]
            ranked = ok(await self.arank_documents(rerank_query, docs))
            return list(ranked)[: config.limit]

        docs = list(ok(await self.afetch_document(queries, config)))
        return docs[: config.limit] if docs else []

    async def create_chapters(
        self,
        draft: NovelDraft,
        chapter_plans: List[ChapterPlan],
        characters: List[CharacterCard],
        guidance: Optional[str] = None,
        writing_style_fetch_config: Optional[WritingStyleFetchConfig] = None,
        writing_style_requirement: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> List[str]:
        """Generate chapters with writing style augmentation via RAG.

        Fetches writing style references from LanceDB using script/scene prompts
        as queries. When `writing_style_requirement` is provided, fetched docs
        are reranked against it for relevance.
        """
        await self.inject_docs(chapter_plans, writing_style_fetch_config, writing_style_requirement)

        # Delegate to NovelCompose.create_chapters for actual generation
        return await super().create_chapters(draft, chapter_plans, characters, guidance, **kwargs)

    async def inject_docs(
        self,
        chapter_plans: list[ChapterPlan],
        writing_style_fetch_config: WritingStyleFetchConfig | None,
        writing_style_requirement: str | None,
    ) -> None:
        """Inject writing style documents into chapter scripts and scenes in-place.

        All script-level and scene-level fetches run concurrently. Each closure
        captures its query (before mutation) and target, fetches, then injects.
        """
        config = writing_style_fetch_config or WritingStyleFetchConfig.default()

        async def _inject_script(plan: ChapterPlan) -> None:
            query = plan.script.as_prompt()  # capture before mutation
            docs = await self._fetch_style_docs(query, config, writing_style_requirement)
            if docs:
                plan.script.append_global_prompt(
                    "Below is some writing style QA docs that you should imitate to achieve the best quality, in chapter scope"
                ).bulk_append_global_prompt([doc.as_prompt() for doc in docs])
            logger.debug(f"Chapter {plan.chapter_index}: injected {len(docs)} script-level style(s)")

        async def _inject_scene(sc: Scene) -> None:
            query = sc.description  # capture before mutation
            docs = await self._fetch_style_docs(query, config, writing_style_requirement)
            if docs:
                sc.append_prompt(
                    "Below is some writing style QA docs that you MUST imitate in this scene to achieve the best quality, in scene scope"
                ).bulk_append([doc.as_prompt() for doc in docs])

        tasks = []
        for cp in chapter_plans:
            tasks.append(_inject_script(cp))
            for scene in cp.script.scenes:
                tasks.append(_inject_scene(scene))

        await asyncio.gather(*tasks)
