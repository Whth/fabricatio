"""Novel RAG capabilities combining novel composition with retrieval-augmented generation."""

from abc import ABC
from asyncio import gather
from typing import List, Optional, Unpack

from fabricatio_core.utils import cfg

cfg(["lancedb"])
from fabricatio_character.models.character import CharacterCard  # noqa: I001
from fabricatio_core import logger
from fabricatio_novel.models.novel_rag import WritingStyleDocument, WritingStyleFetchConfig

from fabricatio_core.utils import ok
from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbRAG

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.kwargs_types import NovelRAGKwargs
from fabricatio_novel.models.plan import ChapterPlan


class NovelComposeRAG(
    LancedbRAG[WritingStyleDocument, LancedbAddRAGConfig, WritingStyleFetchConfig], NovelCompose, ABC
):
    """Novel composition capability extended with writing style RAG support."""

    async def fetch_and_rerank(
        self, query: str, config: WritingStyleFetchConfig, use_reranker: bool
    ) -> List[WritingStyleDocument]:
        """Fetch writing style documents, optionally reranking the results.

        When use_reranker=True, embedding search fetches limit * rerank_scale_factor docs,
        then the reranker filters down to the original limit.
        """
        if use_reranker:
            scaled = config.model_copy(update={"limit": int(config.limit * novel_config.rerank_scale_factor)})
            docs = list(ok(await self.afetch_document(query, scaled)))
            if not docs:
                return docs
            reranked = ok(await self.arank_documents(query, docs))
            return list(reranked)[: config.limit]
        return list(ok(await self.afetch_document(query, config)))

    async def create_chapters(
        self,
        draft: NovelDraft,
        chapter_plans: List[ChapterPlan],
        characters: List[CharacterCard],
        guidance: Optional[str] = None,
        **kwargs: Unpack[NovelRAGKwargs[str]],
    ) -> List[str]:
        """Generate chapters with writing style augmentation via RAG.

        Between script generation and chapter generation, retrieves writing
        style references from LanceDB and injects them into script/scene prompts.
        """
        config = kwargs.pop("writing_style_fetch_config", WritingStyleFetchConfig.default())
        use_reranker = kwargs.pop("use_reranker", False)

        for cp in chapter_plans:
            # Capture query before mutation — append_global_prompt changes as_prompt() output
            script_query = cp.script.as_prompt()
            script_docs = await self.fetch_and_rerank(script_query, config, use_reranker)
            for doc in script_docs:
                cp.script.append_global_prompt(doc.as_prompt())
            logger.debug(f"Chapter {cp.chapter_index}: injected {len(script_docs)} script-level style(s)")

            # Scene-level: fetch per scene based on scene.description → scene.prompt
            scene_results = await gather(
                *(self.fetch_and_rerank(scene.description, config, use_reranker) for scene in cp.script.scenes)
            )
            for scene, scene_docs in zip(cp.script.scenes, scene_results, strict=True):
                scene.bulk_append([doc.as_prompt() for doc in scene_docs])
        # Delegate to NovelCompose.create_chapters for actual generation
        return await super().create_chapters(draft, chapter_plans, characters, guidance, **kwargs)
