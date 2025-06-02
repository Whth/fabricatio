"""Module containing configuration classes for fabricatio-anki."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class AnkiConfig:
    """Configuration for fabricatio-anki."""

    make_deck_creation_proposal_template: str = "make_deck_creation_proposal"
    """Template name for make deck creation proposal."""

    generate_anki_card_type_template: str = "generate_anki_card_type"
    """Template name for generate anki card type."""
    
anki_config = CONFIG.load("anki", AnkiConfig)
__all__ = ["anki_config"]
