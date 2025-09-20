"""Rust bindings for the Rust API of fabricatio-novel."""

from pathlib import Path

class NovelBuilder:
    """A Python-exposed builder for creating EPUB novels."""

    def __init__(self) -> None:
        """Creates a new uninitialized NovelBuilder instance."""

    def new_novel(self) -> NovelBuilder:
        """Initializes a new EPUB novel builder.

        Raises:
            RuntimeError: If initialization fails.
        """

    def set_title(self, title: str) -> NovelBuilder:
        """Sets the novel title.

        Raises:
            RuntimeError: If novel is not initialized.
        """
    def add_author(self, author: str) -> NovelBuilder:
        """Adds an author to the novel metadata.

        Raises:
            RuntimeError: If novel is not initialized.
        """

    def add_chapter(self, title: str, content: str) -> NovelBuilder:
        """Adds a chapter with given title and content.

        Raises:
            RuntimeError: If novel is not initialized or chapter creation fails.
        """

    def add_description(self, description: str) -> NovelBuilder:
        """Adds a description to the novel metadata.

        Raises:
            RuntimeError: If novel is not initialized.
        """

    def add_cover_image(self, path: str | Path, source: str | Path) -> NovelBuilder:
        """Adds a cover image from the given file path.

        Args:
            path: Path inside EPUB where image will be stored (e.g., "cover.png").
            source: Filesystem path to the image file to read.

        Raises:
            RuntimeError: If novel not initialized, file read fails, or adding image fails.
        """

    def add_metadata(self, key: str, value: str) -> NovelBuilder:
        """Adds custom metadata key-value pair to the novel.

        Raises:
            RuntimeError: If novel is not initialized or metadata is invalid.
        """

    def set_stylesheet(self, stylesheet: str) -> NovelBuilder:
        """Sets the CSS stylesheet for the novel.

        Raises:
            RuntimeError: If novel is not initialized or stylesheet processing fails.
        """

    def add_inline_toc(self) -> NovelBuilder:
        """Enables inline table of contents generation.

        Raises:
            RuntimeError: If novel is not initialized.
        """

    def export(self, path: str | Path) -> NovelBuilder:
        """Exports the built novel to the specified file path.

        Raises:
            RuntimeError: If novel not initialized, generation fails, or file write fails.
        """
