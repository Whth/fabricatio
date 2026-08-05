"""Chapter context model — the per-run channel threaded through create_chapters."""

from fabricatio_character.models.mental import MentalState
from fabricatio_core.models.generic import Base


class ChapterContext(Base):
    """Per-run channel threaded through the create_chapters pipeline.

    Carries mutable, stage-evolving state (e.g. character mental states)
    between the :meth:`prepare_chapter_prompt` and
    :meth:`after_chapter_summarize` hooks without requiring closures or
    instance attributes.
    """

    character_states: dict[str, MentalState] | None = None
    """Per-character mental states, evolved after each chapter summary."""
