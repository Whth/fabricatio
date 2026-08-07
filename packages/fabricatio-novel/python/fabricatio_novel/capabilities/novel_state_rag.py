"""Combined RAG + state consistency capability for novel composition.

Applies writing style RAG injection and character state consistency through
the sealed chapter channel: :class:`StateRAGChapterContext` carries both the
state histories and the RAG fetch config, and the two mixins compose on the
base hooks — RAG's ``prepare_chapter_prompt`` (fetch + inject current chapter,
then ``super()``) renders with State's ``extra_chapter_prompt_vars``
(character state board) merged by the base implementation, and State's
``after_chapter_gen`` gate audits the raw prose (re-running the RAG fetch for
the regeneration prompt when a rewrite is needed).
"""

from abc import ABC
from typing import List

from fabricatio_core.utils import cfg

cfg(["lancedb"])
from fabricatio_character.models.character import CharacterCard  # noqa: I001
from fabricatio_novel.capabilities.novel_rag import RAGChapterContext, NovelComposeRAG
from fabricatio_novel.capabilities.novel_state import StateChapterContext, NovelComposeState


class StateRAGChapterContext(StateChapterContext, RAGChapterContext):
    """Chapter context carrying both state tracking fields and RAG writing style config.

    The caller seeds the RAG fetch config / rerank target (state histories
    start empty) and passes it as ``context`` to ``create_chapters`` — both
    mixin hooks narrow via ``isinstance`` and observe their own slice of this
    one channel.
    """


class NovelComposeStateRAG(
    NovelComposeState,
    NovelComposeRAG,
    ABC,
):
    """Novel composition with both writing style RAG and character state consistency.

    No hook overrides needed: RAG's ``prepare_chapter_prompt`` (fetch +
    in-place script/scene injection, then ``super()``) and State's
    ``extra_chapter_prompt_vars`` / ``after_chapter_gen`` compose via the base
    implementation. ``compose_novel`` builds a :class:`StateRAGChapterContext`
    through :meth:`build_chapter_context` — state needs no seeding, and the
    RAG fetch config is caller-set on the channel (or defaulted per render).
    """

    async def build_chapter_context(self, characters: List[CharacterCard]) -> StateRAGChapterContext:
        """Build the caller-owned combined channel (state tracking + RAG config)."""
        return StateRAGChapterContext()
