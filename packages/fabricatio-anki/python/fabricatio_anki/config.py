"""Module containing configuration classes for fabricatio-anki."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class AnkiConfig:
    """Configuration for fabricatio-anki."""

    generate_anki_card_template_template: str = "generate_anki_card_template"
    """Template name for generate anki card type."""

    generate_anki_model_name_template: str = "generate_anki_model_name"
    """Template name for generate anki model name."""
    generate_anki_card_template_generation_requirements_template: str = (
        "generate_anki_card_template_generation_requirements"
    )

    generate_anki_deck_metadata_template: str = "generate_anki_deck_metadata"
    """Template name for generate anki deck metadata."""

    generate_anki_model_generation_requirements_template: str = "generate_anki_model_generation_requirements"
    """ Template name for generate anki model generation requirements."""


anki_config = CONFIG.load("anki", AnkiConfig)
__all__ = ["anki_config"]
