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

from fabricatio_anki.rust import save_template


class Template(SketchedAble, Named):
    """Template model for Anki card templates with HTML, JavaScript, and CSS components."""

    front: str
    """HTML content for the front face of the card.
    Contains text, images, and structure with support for dynamic placeholders.
    Combined with front_js and wrapped in script tags when saved."""

    front_js: str
    """JavaScript code for the front face of the card.
    Enables interactive behavior and dynamic functionality.
    Automatically embedded within the front HTML content when saved."""

    back: str
    """HTML content for the back face of the card.
    Displays answer information with placeholders for dynamic content.
    Combined with back_js and wrapped in script tags when saved."""

    back_js: str
    """JavaScript code for the back face of the card.
    Provides interactive elements and dynamic content manipulation.
    Automatically embedded within the back HTML content when saved."""

    css: str
    """Custom CSS styles controlling the card's visual presentation.
    Defines formatting, fonts, colors, spacing, and layout for both card faces."""

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
            self.assemble(self.front, self.front_js),
            self.assemble(self.back, self.back_js),
            self.css,
        )
        return self

    @staticmethod
    def assemble(side: str, script: str) -> str:
        """Combine HTML content and JavaScript code into a single string.

        This helper method takes HTML content and JavaScript code and combines them by
        appending the JavaScript within script tags at the end of the HTML content.

        Args:
            side (str): The HTML content for a card side (front or back).
            script (str): The JavaScript code to be embedded in the HTML.

        Returns:
            str: The combined HTML content with embedded JavaScript.
        """
        return f"{side}<script>{script}</script>"
