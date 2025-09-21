"""Rust bindings for the Rust API of fabricatio-novel."""

from pathlib import Path
from typing import Self

class NovelBuilder:
    """A Python-exposed builder for creating EPUB novels."""

    def __init__(self) -> None:
        """Creates a new uninitialized NovelBuilder instance."""

    def new_novel(self) -> Self:
        """Initializes a new EPUB novel builder.

        Raises:
            RuntimeError: If initialization fails.
        """

    def set_title(self, title: str) -> Self:
        """Sets the novel title.

        Raises:
            RuntimeError: If novel is not initialized.
        """
    def add_author(self, author: str) -> Self:
        """Adds an author to the novel metadata.

        Raises:
            RuntimeError: If novel is not initialized.
        """

    def add_chapter(self, title: str, content: str) -> Self:
        """Adds a chapter with given title and content.

        Raises:
            RuntimeError: If novel is not initialized or chapter creation fails.
        """

    def set_description(self, description: str) -> Self:
        """Sets the novel description.

        Raises:
            RuntimeError: If novel is not initialized.
        """

    def add_cover_image(self, path: str | Path, source: str | Path) -> Self:
        """Adds a cover image from the given file path.

        Args:
            path: Path inside EPUB where image will be stored (e.g., "cover.png").
            source: Filesystem path to the image file to read.

        Raises:
            RuntimeError: If novel not initialized, file read fails, or adding image fails.
        """

    def add_metadata(self, key: str, value: str) -> Self:
        """Adds custom metadata key-value pair to the novel.

        Raises:
            RuntimeError: If novel is not initialized or metadata is invalid.
        """

    def add_css(self, css: str) -> Self:
        """Adds custom CSS to the novel.

        Args:
            css: A string containing the CSS content to be added.

        Raises:
            RuntimeError: If novel is not initialized or CSS addition fails.
        """

    def add_resource(self, path: str | Path, source: str | Path) -> Self:
        """Add a resource to the EPUB.

        Args:
            path: Internal EPUB path (e.g. 'images/cover.jpg').
            source: Filesystem path to read from.

        Returns:
            Self for chaining.
        """

    def add_font(self, font_family: str, source: str | Path) -> Self:
        """Embed a font and add @font-face CSS rule.

        Font saved as 'fonts/{font_family}.ttf'.

        Args:
            font_family: Name used in CSS and filename.
            source: TTF font file on disk.

        Returns:
            Self for chaining.
        """

    def add_inline_toc(self) -> Self:
        """Enables inline table of contents generation.

        Raises:
            RuntimeError: If novel is not initialized.
        """

    def export(self, path: str | Path) -> Self:
        """Exports the built novel to the specified file path.

        Raises:
            RuntimeError: If novel not initialized, generation fails, or file write fails.
        """

def text_to_xhtml_paragraphs(source: str) -> str:
    """Converts plain text to XHTML paragraphs.

    Args:
        source: Plain text to convert.

    Returns:
        XHTML string with paragraphs.
    """
