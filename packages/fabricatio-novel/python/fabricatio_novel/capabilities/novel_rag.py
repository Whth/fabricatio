"""Novel RAG capabilities combining novel composition with retrieval-augmented generation.

The writing style RAG injection lives on the chapter prompt hook: the caller
builds a :class:`RAGChapterContext` (config + rerank target) and passes it as
``context`` to ``create_chapters``; :meth:`NovelComposeRAG.prepare_chapter_prompt`
fetches style docs for the CURRENT chapter and appends them to its
script/scene prompts in-place, then delegates to the base implementation so
sibling mixins (e.g. mental states) still contribute via
``extra_chapter_prompt_vars``. The capability itself stays stateless — all
per-run configuration threads through the caller-owned channel.
"""

import asyncio
from abc import ABC
from typing import List, Optional

from fabricatio_core.utils import cfg

from fabricatio_novel.models.scripting import Scene

cfg(["lancedb"])
from fabricatio_core import TEMPLATE_MANAGER, logger  # noqa: I001
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.chapter_context import ChapterContext
from fabricatio_novel.models.novel_rag import WritingStyleDocument, WritingStyleFetchConfig
from fabricatio_novel.models.plan import ChapterPlan

from fabricatio_core.utils import ok
from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbRAG


class RAGChapterContext(ChapterContext):
    """Chapter context extended with per-run writing style RAG configuration.

    The caller builds it (optionally combined with other mixins, e.g.
    ``MentalRAGChapterContext``) and passes it as ``context`` to
    :meth:`NovelCompose.create_chapters`; the RAG prompt hook reads the
    config fields to fetch style docs for each chapter.
    """

    writing_style_fetch_config: Optional[WritingStyleFetchConfig] = None
    """Optional fetch configuration override for writing style retrieval."""

    writing_style_requirement: Optional[str] = None
    """Optional rerank target for fetched style docs (None = no reranking)."""


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
        q = TEMPLATE_MANAGER.render_template(
            novel_config.writing_style_query_refine_template,
            {"query": query, "rerank_query": rerank_query},
        )

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

    async def prepare_chapter_prompt(self, ctx: ChapterContext) -> str:
        """Hook: inject writing style docs for the current chapter, then delegate.

        Fetches style references for the current chapter's script and scenes
        (fetch config + rerank target read from the caller-owned
        :class:`RAGChapterContext`) and appends them to the plan's
        script/scene prompts in-place, so they flow into the rendered
        ``{{script}}`` block. Then delegates to the base implementation so
        sibling mixins (e.g. mental states) still contribute via
        :meth:`extra_chapter_prompt_vars`.
        """
        if isinstance(ctx, RAGChapterContext):
            plan = ctx.chapter_plan()
            if plan is not None:
                config = ctx.writing_style_fetch_config or WritingStyleFetchConfig.default()
                await self._inject_style_docs(plan, config, ctx.writing_style_requirement)
        return await super().prepare_chapter_prompt(ctx)

    async def _inject_style_docs(
        self,
        plan: ChapterPlan,
        config: WritingStyleFetchConfig,
        writing_style_requirement: Optional[str],
    ) -> None:
        """Fetch writing style docs for one chapter's script and scenes and inject them in-place.

        The script-level and scene-level fetches run concurrently. Each closure
        captures its query (before mutation) and target, fetches, then injects.
        """

        async def _inject_script() -> None:
            query = plan.script.as_prompt()  # capture before mutation
            docs = await self._fetch_style_docs(query, config, writing_style_requirement)
            if docs:
                inject_sentence = TEMPLATE_MANAGER.render_template(
                    novel_config.writing_style_inject_script_template, {}
                )
                plan.script.append_global_prompt(inject_sentence).bulk_append_global_prompt(
                    [doc.as_prompt() for doc in docs]
                )
            logger.debug(f"Chapter {plan.chapter_index}: injected {len(docs)} script-level style(s)")

        async def _inject_scene(sc: Scene) -> None:
            query = sc.description  # capture before mutation
            docs = await self._fetch_style_docs(query, config, writing_style_requirement)
            if docs:
                inject_sentence = TEMPLATE_MANAGER.render_template(novel_config.writing_style_inject_scene_template, {})
                sc.append_prompt(inject_sentence).bulk_append([doc.as_prompt() for doc in docs])

        await asyncio.gather(_inject_script(), *(_inject_scene(sc) for sc in plan.script.scenes))
