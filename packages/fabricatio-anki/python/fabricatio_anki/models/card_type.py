"""Provide Card model."""

from fabricatio_core.models.generic import SketchedAble


class CardType(SketchedAble):
    """Anki Card template."""

    front: str
    """Represents the front face content of the card, in HTML format.
    This field contains the primary content displayed on the front side of the flashcard,
    usually consisting of text, images, or structured HTML elements. It supports dynamic
    placeholders that can be replaced with actual values during card generation."""
    back: str
    """Represents the back face content of the card, typically in HTML format.
    This field defines the information displayed on the reverse side of the flashcard.
    It may contain placeholders for dynamic data fields and styling instructions.
    The back side often includes detailed explanations, additional context, or supplementary
    media elements that complement the content on the front side."""

    css: str
    """Custom CSS styles for the card's appearance.
    This field holds cascading style sheet rules that define the visual presentation
    of both front and back faces of the card. The CSS ensures consistent formatting
    and allows customization of fonts, colors, spacing, and layout.
    It enables precise control over the design and styling to match specific aesthetic
    preferences or functional requirements."""
