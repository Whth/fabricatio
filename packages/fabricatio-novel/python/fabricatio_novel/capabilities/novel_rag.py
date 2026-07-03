"""Novel RAG capabilities combining novel composition with retrieval-augmented generation."""

from abc import ABC
from asyncio import gather
from typing import List, Optional, Unpack

from fabricatio_core.utils import cfg, fallback_kwargs

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

    async def _fetch_multi_query(
        self,
        queries: List[str],
        config: WritingStyleFetchConfig,
        use_reranker: bool,
    ) -> List[WritingStyleDocument]:
        """Fetch documents for each query variant, dedupe by content, optionally rerank.

        Used when `WritingStyleFetchConfig.use_refined_query=True` and the user has
        supplied a `writing_style_query`: the LLM refines the raw query into N variants,
        and each variant is searched independently. Results are merged (preserving the
        best rank across variants) and optionally reranked against the raw query.
        """
        if not queries:
            return []
        seen: dict[str, WritingStyleDocument] = {}
        per_query_results = await gather(*(self.fetch_and_rerank(q, config, use_reranker) for q in queries))
        for docs in per_query_results:
            for doc in docs:
                if doc.content not in seen:
                    seen[doc.content] = doc
        merged = list(seen.values())
        if use_reranker and len(merged) > config.limit:
            reranked = ok(await self.arank_documents(queries[0], merged))
            return list(reranked)[: config.limit]
        return merged[: config.limit]

    async def _refine_writing_style_query(
        self,
        writing_style_query: str,
        config: WritingStyleFetchConfig,
    ) -> List[str]:
        """Refine a raw user writing-style query into N semantically-diverse variants.

        Returns the original query unchanged if `arefined_query` yields nothing usable,
        so the caller always has at least one query to search with. Failures are logged
        and treated as a no-op — refinement is a best-effort retrieval enhancement.
        """
        try:
            refined = await self.arefined_query(
                writing_style_query,
                k=config.refined_query_count,
            )
        except Exception as exc:  # noqa: BLE001 — refinement is best-effort
            logger.warn(f"Query refinement failed; falling back to raw query: {exc}")
            return [writing_style_query]
        refined_list = [q.strip() for q in (refined or []) if q and q.strip()]
        if not refined_list:
            logger.debug("Query refinement returned empty; using raw query")
            return [writing_style_query]
        logger.info(f"Refined writing-style query into {len(refined_list)} variant(s)")
        return refined_list

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

        When `writing_style_query` is provided AND
        `WritingStyleFetchConfig.use_refined_query=True`, the raw query is refined
        into multiple variants by the LLM and each variant is searched. Otherwise
        retrieval uses the script-level and scene-level prompts as queries.
        """
        # `fallback_kwargs` returns a merged view: caller-supplied values win,
        # listed defaults fill any missing keys. The router discards unknown
        # kwargs, so we can forward the merged dict straight to super().
        merged = fallback_kwargs(
            kwargs,
            writing_style_fetch_config=WritingStyleFetchConfig.default(),
            use_reranker=False,
            writing_style_query=None,
        )
        config = merged["writing_style_fetch_config"]
        use_reranker = merged["use_reranker"]
        writing_style_query = merged["writing_style_query"]
        kwargs = merged
        # Pre-compute refined query variants ONCE for the whole batch when enabled.
        # Both conditions are required: a raw user query AND opt-in refinement.
        refined_queries: Optional[List[str]] = None
        if config.use_refined_query and writing_style_query:
            refined_queries = await self._refine_writing_style_query(writing_style_query, config)

        def _queries_for(base_query: str) -> List[str]:
            """Return the query list to search for a given base (script or scene) query."""
            if refined_queries is not None:
                return refined_queries
            return [base_query]

        for cp in chapter_plans:
            # Capture query before mutation — append_global_prompt changes as_prompt() output
            script_query = cp.script.as_prompt()
            script_docs = await self._fetch_multi_query(_queries_for(script_query), config, use_reranker)
            for doc in script_docs:
                cp.script.append_global_prompt(doc.as_prompt())
            logger.debug(f"Chapter {cp.chapter_index}: injected {len(script_docs)} script-level style(s)")

            # Scene-level: fetch per scene based on scene.description → scene.prompt
            scene_query_lists = [_queries_for(scene.description) for scene in cp.script.scenes]
            scene_results = await gather(
                *(self._fetch_multi_query(qs, config, use_reranker) for qs in scene_query_lists)
            )
            for scene, scene_docs in zip(cp.script.scenes, scene_results, strict=True):
                scene.bulk_append([doc.as_prompt() for doc in scene_docs])
        # Delegate to NovelCompose.create_chapters for actual generation
        return await super().create_chapters(draft, chapter_plans, characters, guidance, **kwargs)
