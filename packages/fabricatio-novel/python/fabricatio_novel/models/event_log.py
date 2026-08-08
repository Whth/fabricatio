"""Event-log models — the novel's body and memory substrate.

Design spec ``2026-08-08-novel-gen-overhaul-design.md`` §4: one data
structure, two roles — the event log IS the novel (append-only, events are
the generation unit) and the memory base (the line web is a fold projection,
replayable from the active chain).

Persistence is workflow-owned (D17): :class:`EventLog` is an in-memory
:class:`PersistentAble` model checkpointed by workflow Actions
(``PersistentAll`` at chapter/checkpoint boundaries, resume via
``RetrieveFromLatest``); append-only is an in-memory invariant, not a
streaming-file concern. :class:`LineWeb` is a derived projection and is
never persisted.
"""

from typing import Dict, List, Optional, Self, Tuple

from fabricatio_capabilities.models.generic import PersistentAble
from fabricatio_core.models.generic import Base
from pydantic import Field

from fabricatio_novel.models.scripting import Scene


class StoryEvent(Base):
    """One event — the minimum generation unit (a scene/beat, ~300-800 chars).

    A chapter is a VIEW: the grouping of its events with a title. Event text
    lives IN the log (``content``) — the log is self-contained; replay =
    read the log. Chapter files become derived exports.
    """

    seq: int
    """Globally monotonic sequence number — unique in the log (append-only guarantees)."""

    parent: Optional[int] = None
    """Seq of the predecessor event on this timeline — events chain up to the head."""

    chapter: Optional[int] = None
    """Chapter (view grouping) this event belongs to."""

    group: str
    """scene (generation unit) | chapter (chapter-end summary) | amend (correction)."""

    intent: Optional[str] = None
    """Event-level contract: what this beat must achieve (覆盖性对照基线)."""

    content: str
    """Event body — free text, no nested structure (D8)."""

    lines: Dict[str, str] = Field(default_factory=dict)
    """Line id → line state snapshot AFTER this event (state = latest snapshot)."""

    characters: List[str] = Field(default_factory=list)
    """Character names present in this event."""

    source: str
    """writer (draft) | verifier (derived summary) | amend (correction)."""


class ChapterContract(Base):
    """Chapter-level contract (两级别契约的章级): 章末目标态 + 活跃线名单.

    Declared before the chapter is split, verified after it completes. The
    splitter consumes it together with the outline synopsis, a memory slice,
    and the lines' current states (§4.3a).
    """

    chapter_index: int
    """Zero-based chapter index."""

    synopsis: str = ""
    """本章大纲 — the chapter's outline synopsis (splitter input)."""

    target_state: str = ""
    """章末目标态 — where the chapter must land by its end."""

    active_lines: List[str] = Field(default_factory=list)
    """活跃线名单 — the lines this chapter is declared to move."""


class EventIntent(Base):
    """Splitter output unit: 1+ consecutive scenes grouped into one event.

    Grouping rule (deterministic code): consecutive scenes sharing
    ``location``/``when`` with a weight-sum within bounds form one event.
    Verification/回炉 granularity is the event (union of its scenes).
    """

    scenes: List[Scene]
    """The grouped consecutive scenes."""

    intent: str = ""
    """What this event must achieve (coverage对照基线)."""

    line_targets: Dict[str, str] = Field(default_factory=dict)
    """Union of the scenes' line_targets: line → target state (declared baseline)."""


class EventLog(PersistentAble):
    """Append-only in-memory event log with branching/backtracking (git model).

    Truth is never mutated — corrections are AMEND events. The timeline is a
    pointer layer: ``head_seq`` = the current tip; backtracking moves the
    head and leaves later events as a DEAD branch (queryable for reference,
    excluded from fold and context).
    """

    events: List[StoryEvent] = Field(default_factory=list)
    """All events ever generated — never deleted."""

    head_seq: int = 0
    """Current timeline tip seq (0 = empty log; the first event's seq is 1)."""

    branches: Dict[str, int] = Field(default_factory=dict)
    """Branch label → tip seq. v1: mechanism only, no comparison UI (D10: no human)."""

    def append(self, event: StoryEvent) -> Self:
        """Record the event on the active chain and advance the head to it.

        The caller assigns ``seq = next_seq()`` and ``parent = head_seq``
        before appending — the log never rewrites the event.

        Args:
            event: The event to append (its seq must be ``next_seq()``).
        """
        ...

    def backtrack(self, to_seq: int) -> Self:
        """Move the head to ``to_seq``; later events stay as a dead branch.

        Args:
            to_seq: The seq to rewind the active chain to.
        """
        ...

    def mark_branch(self, label: str) -> Self:
        """Save the current head under ``label`` as a branch point."""
        ...

    def switch_branch(self, label: str) -> Self:
        """Move the head to the tip saved under ``label`` (v1 mechanism)."""
        ...

    def active(self) -> List[StoryEvent]:
        """The current timeline: walk the parent chain from ``head_seq``, oldest first."""
        ...

    def query(
        self,
        group: Optional[str] = None,
        line: Optional[str] = None,
        chapter: Optional[int] = None,
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[StoryEvent]:
        """Filter the FULL log (dead branches included) by the given criteria.

        Args:
            group: Only events of this group (scene/chapter/amend).
            line: Only events carrying this line id in ``lines``.
            chapter: Only events of this chapter.
            since: Only events with ``seq >= since``.
            limit: Cap the result length.
        """
        ...

    def recent(self, limit: int = 3) -> List[StoryEvent]:
        """Tail of the ACTIVE chain — the 近程 slice of the context budget (§4.4)."""
        ...

    def distant_memory(self, line_ids: List[str], limit: int = 3) -> List[StoryEvent]:
        """远记忆: chapter-summary events of OLD chapters where the given lines moved.

        Deterministic line-trail selection (D14): active lines → the old
        chapters where they moved → those chapters' summaries. Pure log
        queries, zero embeddings. RAG semantic retrieval is an OPTIONAL
        capability mixin that replaces/augments this within the same budget.
        """
        ...

    def next_seq(self) -> int:
        """Next globally monotonic seq (max seq + 1; 1 on an empty log)."""
        ...

    def fold_lines(self) -> "LineWeb":
        """Fold the ACTIVE chain into the line web (dead branches never touch it)."""
        ...


class LineView(Base):
    """A line: a tag plus the state snapshots carried by its events (统一线形式).

    No type registry — ``type`` is an optional free-text label the LLM
    writes and code never depends on (D8).
    """

    id: str
    """Line id (e.g. '林川-苏婉')."""

    type: str = ""
    """Optional free-text label (relationship / character / plot / ...)."""

    status: str = "active"
    """active | dormant | closed."""

    current: str = ""
    """Latest snapshot on the line — folded over the ACTIVE chain only."""

    history: List[Tuple[int, Optional[int], str]] = Field(default_factory=list)
    """(seq, chapter, state_snapshot) — the line's event trail."""


class LineWeb(Base):
    """Fold projection of the active chain (§4.5) — derived, never persisted.

    Lifecycle: born (contract pre-declares, or verifier proposes + drift-
    triggered sync registers it into the bible), dormant (no events),
    closed (payoff → stops injecting). 伏笔 open→paid is a foreshadow line's
    lifecycle.
    """

    lines: Dict[str, LineView] = Field(default_factory=dict)
    """Line id → :class:`LineView`."""

    def line(self, line_id: str) -> Optional[LineView]:
        """The line's view, if registered."""
        ...

    def active_lines(self, limit: int = 5) -> List[LineView]:
        """Active lines (contract-declared first) — the 线状态 slice of the context budget (§4.4)."""
        ...

    def current_state(self, line_id: str) -> Optional[str]:
        """The line's current state snapshot, if any."""
        ...

    def close_line(self, line_id: str) -> Self:
        """Mark the line closed (payoff → stops injecting into context)."""
        ...
