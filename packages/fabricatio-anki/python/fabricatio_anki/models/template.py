"""Template model.

This module defines the Template class, which represents a card template in the Anki
model system. The Template class includes content for the front and back faces of a card,
as well as custom CSS styles for visual presentation. It also provides functionality to save
the template to a specified directory.

Classes:
    Template: Represents an Anki card template with front, back, and CSS content.
"""

from pathlib import Path
from typing import Self

from fabricatio_core.models.generic import Named, SketchedAble

from fabricatio_anki.rust import save_template


class Template(SketchedAble, Named):
    """Template model."""

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

    def save_to(self, parent_dir: Path | str) -> Self:
        """Save the current card type to the specified directory.

        This method persists the card's front, back, and CSS content using
        the provided parent directory. It constructs the file path by combining
        the parent directory with the card type's name.

        Args:
            parent_dir (Path): The directory where the card type will be saved.

        Returns:
            Self: Returns the instance of the current CardType for method chaining.
        """
        save_template(Path(parent_dir) / self.name, self.front, self.back, self.css)
        return self
