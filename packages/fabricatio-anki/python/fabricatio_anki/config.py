"""Module containing configuration classes for fabricatio-anki."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class AnkiConfig:
    """Configuration class for fabricatio-anki.

    This class holds the configuration settings required for generating Anki cards, models,
    and decks. Each field corresponds to a template used in different stages of Anki object creation.

    Note:
        - Incorrect template names can lead to failures during Anki object generation.
        - Ensure all template names are correctly set according to your use case.
    """

    generate_anki_card_front_side_template: str = "built-in/generate_anki_card_front_side"
    """
    The template name used for generating the front side of Anki cards.

    If this value is incorrect or missing, Anki card front side generation will fail.
    """

    generate_anki_card_back_side_template: str = "built-in/generate_anki_card_back_side"
    """
    The template name used for generating the back side of Anki cards.

    If this value is incorrect or missing, Anki card back side generation will fail.
    """

    generate_anki_card_template_template: str = "built-in/generate_anki_card_template"
    """
    The template name used for generating Anki card types.

    If this value is incorrect or missing, Anki card generation will fail.
    """

    generate_anki_model_name_template: str = "built-in/generate_anki_model_name"
    """
    The template name used for generating Anki model names.

    If this value is incorrect or missing, Anki model generation will fail.
    """

    generate_anki_card_template_generation_requirements_template: str = (
        "built-in/generate_anki_card_template_generation_requirements"
    )
    """
    The template name used for generating Anki card template generation requirements.

    If this value is incorrect or missing, Anki card template generation will fail.
    """

    generate_anki_deck_metadata_template: str = "built-in/generate_anki_deck_metadata"
    """
    The template name used for generating Anki deck metadata.

    If this value is incorrect or missing, Anki deck metadata generation will fail.
    """

    generate_anki_model_generation_requirements_template: str = "built-in/generate_anki_model_generation_requirements"
    """
    The template name used for generating Anki model generation requirements.

    If this value is incorrect or missing, Anki model generation will fail.
    """

    topic_analysis_assemble_template: str = "built-in/topic_analysis_assemble"
    """The template name used for assembling topic analysis."""

    generate_topic_analysis_template: str = "built-in/generate_topic_analysis"
    """The template name used for generating analysis."""


anki_config = CONFIG.load("anki", AnkiConfig)
__all__ = ["anki_config"]
