"""Combined RAG + Mental state capability for novel composition.

Applies writing style RAG injection into chapter scripts, then generates
chapters with mental state tracking (seed → inject → evolve per chapter).
"""

from abc import ABC
from typing import TYPE_CHECKING, Dict, List, Unpack

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import logger
from fabricatio_core.utils import cfg

cfg(["lancedb"])
from fabricatio_novel.capabilities.novel_mental import NovelComposeMental
from fabricatio_novel.capabilities.novel_rag import NovelComposeRAG
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.kwargs_types import NovelRAGKwargs
from fabricatio_novel.models.novel_rag import WritingStyleFetchConfig
from fabricatio_novel.models.plan import ChapterPlan

if TYPE_CHECKING:
    from fabricatio_character.models.mental import MentalState


class NovelComposeMentalRAG(
    NovelComposeRAG,
    NovelComposeMental,
    ABC,
):
    """Novel composition with both writing style RAG and mental state tracking.

    create_chapters does RAG injection first (augments scripts with style docs),
    then delegates to NovelComposeMental.create_chapters for mental state
    generation (seed → inject → evolve).

    compose_novel is inherited from NovelComposeMental — it seeds mental states
    and calls self.create_chapters, which resolves to the combined override.
    """

    async def create_chapters(
        self,
        draft: NovelDraft,
        chapter_plans: List[ChapterPlan],
        characters: List[CharacterCard],
        guidance: str | None = None,
        character_states: Dict[str, "MentalState"] | None = None,
        **kwargs: Unpack[NovelRAGKwargs[str]],
    ) -> List[str]:
        """Generate chapters with RAG style injection + mental state tracking.

        1. RAG: fetch writing style docs, inject into script/scene prompts.
        2. Mental: seed/inject/evolve character mental states per chapter.
        """
        config = kwargs.pop("writing_style_fetch_config", WritingStyleFetchConfig.default())
        use_reranker = kwargs.pop("use_reranker", False)

        # RAG injection — augments chapter_plans scripts in-place
        for cp in chapter_plans:
            # Capture query before mutation — append_global_prompt changes as_prompt() output
            script_query = cp.script.as_prompt()
            script_docs = await self.fetch_and_rerank(script_query, config, use_reranker)
            for doc in script_docs:
                cp.script.append_global_prompt(doc.as_prompt())
            logger.debug(f"Chapter {cp.chapter_index}: injected {len(script_docs)} script-level style(s)")

            for scene in cp.script.scenes:
                scene_docs = await self.fetch_and_rerank(scene.description, config, use_reranker)
                for doc in scene_docs:
                    scene.append_prompt(doc.as_prompt())

        # Mental generation — uses augmented scripts + mental states
        return await super().create_chapters(draft, chapter_plans, characters, guidance, character_states, **kwargs)
