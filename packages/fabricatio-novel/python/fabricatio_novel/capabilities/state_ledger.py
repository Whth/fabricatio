"""Sealed state-domain object for character state consistency.

Owns the durable state ledger (histories + violations) and every mutation or
rendering that derives purely from the state domain: the per-chapter commit
rules (``record``), the Character State Board render (``board_context``), and
the previous-states reachability baseline render (``previous_states_context``).

The object is side-effect-free: it never imports ``logger`` — transient
diagnostics belong at the capability callsite, this object only stores and
renders. ``model_dump()`` happens ONLY inside the ``render_template`` engine
boundary (the handlebars pyi contract), never in domain logic.
"""

from typing import Dict, List, Optional, Self, Tuple

from fabricatio_character.models.character import CharacterCard
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.generic import Base
from pydantic import Field

from fabricatio_novel.config import novel_config
from fabricatio_novel.models.chapter_state import ChapterStateRecord, CharacterStateEntry, StateBoard


class StateLedger(Base):
    """Durable, sealed store of per-chapter character state commitments.

    ``histories`` is the complete ordered per-character timeline: exactly one
    ``(chapter_index, end_state)`` entry per committed chapter, recorded or
    carried forward. ``violations`` is the append-only durable union of LLM
    findings and capability-authored failure markers; dedup happens at RENDER
    time, never at store.
    """

    histories: Dict[str, List[Tuple[int, str]]] = Field(default_factory=dict)
    """Global layer: character name -> [(chapter_index, end state), ...] in chapter order."""

    violations: List[str] = Field(default_factory=list)
    """Durable log of human-readable violations across all chapters."""

    def record(self, record: ChapterStateRecord, chapter_index: int, characters: Optional[List[CharacterCard]]) -> Self:
        """Commit one chapter's extraction record to the ledger and return self (chainable).

        Appends each character's end state to the global history (tagged with
        the chapter index), carries forward the previous end state for
        characters absent from the record (re-appended under the current
        chapter index; skipped when they have no history entry), and unions
        the record's violations into the durable store.
        """
        recorded = set()
        for cs in record.characters:
            recorded.add(cs.character)
            history = self.histories.get(cs.character, [])
            self.histories[cs.character] = [*history, (chapter_index, cs.chapter_end_state)]
        known = set(self.histories)
        if characters:
            known |= {card.name for card in characters}
        for name in known - recorded:
            history = self.histories.get(name, [])
            if history:
                self.histories[name] = [*history, (chapter_index, history[-1][1])]
        self.violations.extend(record.violations)
        return self

    def extend_violations(self, violations: List[str]) -> Self:
        """Append violations to the durable store and return self (chainable)."""
        self.violations.extend(violations)
        return self

    def board_context(self, characters: Optional[List[CharacterCard]]) -> str:
        """Render the Character State Board as concise prompt injection."""
        names = set(self.histories)
        if characters:
            names |= {card.name for card in characters}
        board = StateBoard(
            states=[self._board_entry(name, self.histories.get(name, [])) for name in sorted(names)],
            warnings=list(dict.fromkeys(self.violations)),
        )
        return TEMPLATE_MANAGER.render_template(
            novel_config.character_state_board_template,
            board.model_dump(),
        ).strip()

    @staticmethod
    def _board_entry(name: str, history: List[Tuple[int, str]]) -> CharacterStateEntry:
        """Build the board row for one character from its global history."""
        if history:
            idx, state = history[-1]
            return CharacterStateEntry(name=name, state=state, chapter=idx, has_chapter=True)
        return CharacterStateEntry(name=name)

    def previous_states_context(self, characters: Optional[List[CharacterCard]]) -> str:
        """Render per-character previous chapter-end states (reachability baseline)."""
        entries: List[CharacterStateEntry] = []
        if characters is not None:
            entries = [self._board_entry(card.name, self.histories.get(card.name, [])) for card in characters]
        return TEMPLATE_MANAGER.render_template(
            novel_config.chapter_previous_states_template,
            {"states": [entry.model_dump() for entry in entries]},
        ).strip()
