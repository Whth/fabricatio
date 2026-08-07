"""Chapter context model — the sealed per-chapter channel for the chapter pipeline.

The base ``create_chapters`` loop owns this channel: it sets the run-wide
inputs once (``draft`` / ``chapter_plans`` / ``characters`` / ``guidance``)
and accumulates every chapter as a self-describing ``(index, item)`` tuple in
``chapter_summaries`` / ``chapter_contents``. Hooks therefore see ALL chapters
— past, present, and planned — through ONE typed object instead of a long
positional argument list.

The channel is plain DATA: the fields are the single sources of truth, and
per-chapter views (current plan, previous summary/tail, …) are plain methods
(:meth:`ChapterContext.chapter_plan`, :meth:`ChapterContext.previous_summary`,
…) that accept a chapter index (default ``-1`` = the pipeline's current
position / most recently completed chapter) — never stored fields, never
properties, so nothing duplicates anything. Value assignment also goes
through chainable methods (:meth:`ChapterContext.set_draft`,
:meth:`ChapterContext.add_summary`, …): the loop sets the run-wide inputs via
``set_*`` and records history via ``add_*``, so callers never assign fields
directly. The current position (:meth:`ChapterContext.chapter_index`) is the
length of ``chapter_contents`` — the loop appends exactly one tuple per
completed chapter — so the loop never maintains a separate index field that
could drift out of sync. Mixins add their own fields for cross-hook state
(e.g. ``MentalChapterContext`` in
``fabricatio_novel.capabilities.novel_mental``, ``RAGChapterContext`` in
``fabricatio_novel.capabilities.novel_rag``, ``StateChapterContext`` in
``fabricatio_novel.capabilities.novel_state``); the base model itself carries
no mixin-specific state.
"""

from typing import Any, Dict, List, Optional, Self, Tuple

from fabricatio_character.models.character import CharacterCard
from fabricatio_core.models.generic import Base
from pydantic import Field

from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import ChapterSummary
from fabricatio_novel.utils import last_paragraph


class ChapterContext(Base):
    """Sealed per-chapter channel threaded through the create_chapters pipeline.

    Every stage input plus the full run history (all chapter plans, all
    summaries, all generated contents) so any hook can look at ANY chapter.

    The input fields are ``None`` until the base loop populates them (the loop
    invariant: hooks always see them populated) — they default to ``None`` so
    callers can construct the channel with only their own mixin fields (e.g.
    seeded mental states) before the run starts.
    """

    draft: Optional[NovelDraft] = None
    """The novel draft (language, constraints, synopsis). Set by the loop."""

    chapter_plans: Optional[List[ChapterPlan]] = None
    """ALL chapter plans + scripts, in order. Set by the loop once per run."""

    characters: Optional[List[CharacterCard]] = None
    """The full character card list. Set by the loop."""

    guidance: Optional[str] = None
    """Optional per-run writing guidance. Set by the loop."""

    chapter_summaries: List[Tuple[int, ChapterSummary]] = Field(default_factory=list)
    """(chapter_index, summary) pairs for ALL chapters summarized so far, in order.

    Appended by the loop AFTER the summary is generated and BEFORE
    ``after_chapter_summarize`` fires, so the current chapter's summary is
    visible inside that hook. A chapter whose summarize step failed simply has
    no entry.
    """

    chapter_contents: List[Tuple[int, str]] = Field(default_factory=list)
    """(chapter_index, raw content) pairs for ALL chapters generated so far, in order.

    Appended by the loop at the END of each iteration — ``chapter_index`` is
    the length of this list, so appending last keeps the position at the
    chapter being worked on for the whole iteration (both hooks see the same
    position).
    """

    staged_chapter: Optional[Tuple[int, str]] = None
    """The chapter currently being generated, staged as (chapter_index, raw content).

    Set by the loop via :meth:`set_pending_chapter` right before
    :meth:`after_chapter_gen` fires; the hook may replace it; the loop reads it
    back (via :meth:`pending_chapter`) and summarizes the FINAL text. None
    until the first chapter is staged.
    """

    chapter_prompt_vars: Dict[str, Any] = Field(default_factory=dict)
    """Extra template vars for the current chapter-requirement render.

    Populated by ``extra_chapter_prompt_vars`` hook implementations via
    :meth:`add_prompt_vars`; the base ``prepare_chapter_prompt`` merges these
    into the rendered vars and resets them at the start of every render —
    per-render scratch space, not run history.
    """

    # ── Value assignment (chainable methods — the loop never assigns fields) ──

    def set_draft(self, draft: NovelDraft) -> Self:
        """Set the novel draft and return self (chainable)."""
        self.draft = draft
        return self

    def set_chapter_plans(self, chapter_plans: List[ChapterPlan]) -> Self:
        """Set ALL chapter plans and return self (chainable)."""
        self.chapter_plans = chapter_plans
        return self

    def set_characters(self, characters: List[CharacterCard]) -> Self:
        """Set the character card list and return self (chainable)."""
        self.characters = characters
        return self

    def set_guidance(self, guidance: Optional[str]) -> Self:
        """Set the optional writing guidance and return self (chainable)."""
        self.guidance = guidance
        return self

    def add_summary(self, idx: int, summary: ChapterSummary) -> Self:
        """Record a completed chapter's summary as an (idx, summary) pair and return self.

        Called by the loop AFTER the summary is generated and BEFORE
        ``after_chapter_summarize`` fires.
        """
        self.chapter_summaries.append((idx, summary))
        return self

    def add_content(self, idx: int, content: str) -> Self:
        """Record a completed chapter's raw content as an (idx, content) pair and return self.

        Called by the loop at the END of each iteration, so ``chapter_index()``
        stays at the chapter being worked on for the whole iteration.
        """
        self.chapter_contents.append((idx, content))
        return self

    def set_pending_chapter(self, idx: int, content: str) -> Self:
        """Stage a chapter's raw content as the pending (idx, content) tuple and return self.

        Called by the loop right after generation, BEFORE ``after_chapter_gen``
        fires; the hook may call it again to replace the staged text (e.g.
        regeneration), and the loop reads the final text back via
        :meth:`pending_chapter` before summarizing.
        """
        self.staged_chapter = (idx, content)
        return self

    def add_prompt_vars(self, prompt_vars: Dict[str, Any]) -> Self:
        """Merge extra template vars for the current chapter prompt and return self.

        Called by ``extra_chapter_prompt_vars`` hook implementations to
        contribute feature-specific template vars (state boards, mental
        states, …) to the upcoming chapter-requirement render. Vars
        accumulate until the render resets them via :meth:`reset_prompt_vars`.
        """
        self.chapter_prompt_vars.update(prompt_vars)
        return self

    def reset_prompt_vars(self) -> Self:
        """Clear the accumulated chapter prompt vars and return self.

        Called by the base ``prepare_chapter_prompt`` at the start of every
        render so a chapter never sees the previous render's vars.
        """
        self.chapter_prompt_vars.clear()
        return self

    def pending_chapter(self, idx: int = -1) -> Optional[str]:
        """Staged raw content of the chapter currently being generated.

        Available inside :meth:`after_chapter_gen` (the loop stages the text
        right before the hook fires); None otherwise.

        Args:
            idx: -1 (default) for the pipeline's current staged chapter, or an
                absolute chapter index (None if the staged chapter is not that
                index).
        """
        if self.staged_chapter is None:
            return None
        if idx == -1 or self.staged_chapter[0] == idx:
            return self.staged_chapter[1]
        return None

    # ── Views (plain methods over the canonical lists — not stored fields) ──
    # Each view accepts an explicit chapter ``idx`` (default -1 = the pipeline's
    # current position, or the most recently completed chapter for the
    # ``previous_*`` views); a non-negative ``idx`` addresses that absolute
    # chapter, so hooks can inspect ANY chapter of the run.

    def chapter_index(self) -> int:
        """Index of the chapter the pipeline is currently working on.

        The loop appends exactly one (index, content) tuple per completed
        chapter, so the next index to generate is always the history length —
        no separately stored index field to keep in sync.
        """
        return len(self.chapter_contents)

    def chapter_count(self) -> Optional[int]:
        """Total number of chapters planned for this run."""
        return len(self.chapter_plans) if self.chapter_plans is not None else None

    def chapter_plan(self, idx: int = -1) -> Optional[ChapterPlan]:
        """Plan of a chapter: default -1 = the one currently being worked on.

        Args:
            idx: -1 (default) for the current chapter, or an absolute chapter
                index to inspect another chapter's plan.
        """
        if self.chapter_plans is None:
            return None
        pos = self.chapter_index() if idx == -1 else idx
        if 0 <= pos < len(self.chapter_plans):
            return self.chapter_plans[pos]
        return None

    def previous_summary(self, idx: int = -1) -> Optional[ChapterSummary]:
        """Summary of the most recently completed chapter.

        During prompt preparation (:meth:`prepare_chapter_prompt`) that is the
        chapter right before the current one; None until the first chapter is
        summarized. A chapter whose summarize step failed simply leaves the
        previous summary in place.

        Args:
            idx: -1 (default) for the most recently completed chapter, or an
                absolute chapter index (None if that chapter has no summary).
        """
        if idx == -1:
            if not self.chapter_summaries:
                return None
            return self.chapter_summaries[-1][1]
        return self._summary_at(idx)

    def previous_chapter_tail(self, idx: int = -1) -> Optional[str]:
        """Closing paragraphs of the most recently completed chapter.

        Args:
            idx: -1 (default) for the most recently completed chapter, or an
                absolute chapter index (None if that chapter has no content).
        """
        if idx == -1:
            if not self.chapter_contents:
                return None
            return last_paragraph(self.chapter_contents[-1][1])
        for i, content in reversed(self.chapter_contents):
            if i == idx:
                return last_paragraph(content)
            if i < idx:
                break
        return None

    def current_summary(self, idx: int = -1) -> Optional[ChapterSummary]:
        """Summary of the chapter currently being worked on.

        Available once the loop appends it (i.e. inside
        :meth:`after_chapter_summarize`); None before that. The tuple's index
        discriminates it from older summaries.

        Args:
            idx: -1 (default) for the current chapter, or an absolute chapter
                index (None if that chapter has no summary).
        """
        if idx == -1:
            if self.chapter_summaries and self.chapter_summaries[-1][0] == self.chapter_index():
                return self.chapter_summaries[-1][1]
            return None
        return self._summary_at(idx)

    def contents(self) -> List[str]:
        """Raw contents of all completed chapters, unpacked, in chapter order."""
        return [content for _, content in self.chapter_contents]

    def _summary_at(self, idx: int) -> Optional[ChapterSummary]:
        """Summary tagged with the absolute chapter index ``idx``, if any.

        Searches by the tuple index (not list position) so a chapter whose
        summarize step failed simply yields None instead of shifting lookups.
        """
        for i, summary in reversed(self.chapter_summaries):
            if i == idx:
                return summary
            if i < idx:
                break
        return None
