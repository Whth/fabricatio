"""Template model.

This module defines the Template class, which represents a card template in the Anki
model system. The Template class includes content for the front and back faces of a card,
JavaScript code for both sides, as well as custom CSS styles for visual presentation.
It also provides functionality to save the template to a specified directory, automatically
assembling HTML content with embedded JavaScript.

Classes:
    Template: Represents an Anki card template with front, back, JavaScript, and CSS content.
"""

from pathlib import Path
from typing import Self

from fabricatio_core.models.generic import Named, SketchedAble

from fabricatio_anki.rust import extract_html_component, save_template


class Side(SketchedAble):
    """Represents one side of an Anki card with layout, JavaScript, and CSS components."""

    layout: str
    """HTML content for the card side.
    Contains text, images, and structure with support for dynamic placeholders."""
    js: str
    """JavaScript code for the card side.
    Enables interactive behavior and dynamic functionality."""
    css: str
    """CSS styles specific to this card side.
    Defines formatting, colors, spacing, and layout elements."""

    def assemble(self) -> str:
        """Combines HTML content and JavaScript code into a single string.

        Returns:
            str: The assembled HTML content with embedded JavaScript.
        """
        return f"{self.layout}\n<script>{self.js}</script>\n<style>{self.css}</style>"

    @classmethod
    def from_html(cls, source: str) -> Self:
        """Create a Side instance from HTML source by extracting layout, JavaScript, and CSS components."""
        layout, js, css = extract_html_component(source)
        return cls(layout=layout, js=js, css=css)


class Template(SketchedAble, Named):
    """Template model for Anki card templates with HTML, JavaScript, and CSS components."""

    front: Side
    """The front side of the card.
    Contains the question or prompt that will be shown to the user first."""

    back: Side
    """The back side of the card.
    Contains the answer or additional information revealed after the front side."""

    def save_to(self, parent_dir: Path | str) -> Self:
        """Save the current card template to the specified directory.

        This method persists the card's front and back content (each with their associated
        JavaScript automatically embedded) and CSS content to the provided parent directory.
        It constructs the file path by combining the parent directory with the template's name.

        Args:
            parent_dir (Path | str): The directory where the card template will be saved.

        Returns:
            Self: Returns the instance of the current Template for method chaining.
        """
        save_template(
            Path(parent_dir) / self.name,
            self.front.assemble(),
            self.back.assemble(),
        )
        return self
