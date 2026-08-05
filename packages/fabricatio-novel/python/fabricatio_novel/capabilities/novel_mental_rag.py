"""Combined RAG + Mental state capability for novel composition.

Applies writing style RAG injection and mental state tracking through the
sealed chapter channel: :class:`MentalRAGChapterContext` carries both the
seeded mental states and the RAG fetch config, and the two mixins compose on
the base hooks — RAG's ``prepare_chapter_prompt`` (fetch + inject current
chapter, then ``super()``) renders with Mental's ``extra_chapter_prompt_vars``
(character states) merged by the base implementation.
"""

from abc import ABC
from typing import List

from fabricatio_core.utils import cfg

cfg(["lancedb"])
from fabricatio_character.models.character import CharacterCard  # noqa: I001
from fabricatio_novel.capabilities.novel_mental import MentalChapterContext, NovelComposeMental
from fabricatio_novel.capabilities.novel_rag import RAGChapterContext, NovelComposeRAG


class MentalRAGChapterContext(MentalChapterContext, RAGChapterContext):
    """Chapter context carrying both mental states and RAG writing style config.

    The caller seeds ``character_states`` and optionally sets the RAG fetch
    config / rerank target, then passes it as ``context`` to
    ``create_chapters`` — both mixin hooks narrow via ``isinstance`` and
    observe their own slice of this one channel.
    """


class NovelComposeMentalRAG(
    NovelComposeMental,
    NovelComposeRAG,
    ABC,
):
    """Novel composition with both writing style RAG and mental state tracking.

    No hook overrides needed: RAG's ``prepare_chapter_prompt`` (fetch +
    in-place script/scene injection, then ``super()``) and Mental's
    ``extra_chapter_prompt_vars`` / ``after_chapter_summarize`` compose via
    the base implementation. ``compose_novel`` seeds a
    :class:`MentalRAGChapterContext` through :meth:`build_chapter_context`.
    """

    async def build_chapter_context(self, characters: List[CharacterCard]) -> MentalRAGChapterContext:
        """Build the caller-owned combined channel (mental states + RAG config)."""
        return MentalRAGChapterContext(character_states=await self.seed_mental_states(characters))
