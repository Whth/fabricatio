"""Python interface definitions for Rust-based functionality.

This module provides type stubs and documentation for Rust-implemented utilities,
including template rendering, cryptographic hashing, language detection, and
bibliography management. The actual implementations are provided by Rust modules.

Key Features:
- TemplateManager: Handles Handlebars template rendering and management.
- BibManager: Manages BibTeX bibliography parsing and querying.
- Cryptographic utilities: BLAKE3 hashing.
- Text utilities: Word boundary splitting and word counting.
"""

from pathlib import Path
from typing import List, Optional

from pydantic import JsonValue

class TemplateManager:
    """Template rendering engine using Handlebars templates.

    This manager handles template discovery, loading, and rendering
    through a wrapper around the handlebars-rust engine.

    See: https://crates.io/crates/handlebars
    """

    def __init__(
        self, template_dirs: List[Path], suffix: Optional[str] = None, active_loading: Optional[bool] = None
    ) -> None:
        """Initialize the template manager.

        Args:
            template_dirs: List of directories containing template files
            suffix: File extension for templates (defaults to 'hbs')
            active_loading: Whether to enable dev mode for reloading templates on change
        """

    @property
    def template_count(self) -> int:
        """Returns the number of currently loaded templates."""

    def get_template_source(self, name: str) -> Optional[str]:
        """Get the filesystem path for a template.

        Args:
            name: Template name (without extension)

        Returns:
            Path to the template file if found, None otherwise
        """

    def discover_templates(self) -> None:
        """Scan template directories and load available templates.

        This refreshes the template cache, finding any new or modified templates.
        """

    def render_template(self, name: str, data: JsonValue) -> str:
        """Render a template with context data.

        Args:
            name: Template name (without extension)
            data: Context dictionary to provide variables to the template

        Returns:
            Rendered template content as string

        Raises:
            RuntimeError: If template rendering fails
        """

    def render_template_raw(self, template: str, data: JsonValue) -> str:
        """Render a template with context data.

        Args:
            template: The template string
            data: Context dictionary to provide variables to the template

        Returns:
            Rendered template content as string
        """

def blake3_hash(content: bytes) -> str:
    """Calculate the BLAKE3 cryptographic hash of data.

    Args:
        content: Bytes to be hashed

    Returns:
        Hex-encoded BLAKE3 hash string
    """

def detect_language(string: str) -> str:
    """Detect the language of a given string."""

def split_word_bounds(string: str) -> List[str]:
    """Split the string into words based on word boundaries.

    Args:
        string: The input string to be split.

    Returns:
        A list of words extracted from the string.
    """

def word_count(string: str) -> int:
    """Count the number of words in the string.

    Args:
        string: The input string to count words from.

    Returns:
        The number of words in the string.
    """

class BibManager:
    """BibTeX bibliography manager for parsing and querying citation data."""

    def __init__(self, path: str) -> None:
        """Initialize the bibliography manager.

        Args:
            path: Path to BibTeX (.bib) file to load

        Raises:
            RuntimeError: If file cannot be read or parsed
        """

    def get_cite_key(self, title: str) -> Optional[str]:
        """Find citation key by exact title match.

        Args:
            title: Full title to search for (case-insensitive)

        Returns:
            Citation key if exact match found, None otherwise
        """

    def get_cite_key_fuzzy(self, query: str) -> Optional[str]:
        """Find best matching citation using fuzzy text search.

        Args:
            query: Search term to find in bibliography entries

        Returns:
            Citation key of best matching entry, or None if no good match

        Notes:
            Uses nucleo_matcher for high-quality fuzzy text searching
            See: https://crates.io/crates/nucleo-matcher
        """

    def list_titles(self, is_verbatim: Optional[bool] = False) -> List[str]:
        """List all titles in the bibliography.

        Args:
            is_verbatim: Whether to return verbatim titles (without formatting)

        Returns:
            List of all titles in the bibliography
        """

    def get_author_by_key(self, key: str) -> Optional[List[str]]:
        """Retrieve authors by citation key.

        Args:
            key: Citation key

        Returns:
            List of authors if found, None otherwise
        """

    def get_year_by_key(self, key: str) -> Optional[int]:
        """Retrieve the publication year by citation key.

        Args:
            key: Citation key

        Returns:
            Publication year if found, None otherwise
        """

    def get_abstract_by_key(self, key: str) -> Optional[str]:
        """Retrieve the abstract by citation key.

        Args:
            key: Citation key

        Returns:
            Abstract if found, None otherwise
        """
    def get_title_by_key(self, key: str) -> Optional[str]:
        """Retrieve the title by citation key.

        Args:
            key: Citation key

        Returns:
            Title if found, None otherwise
        """

    def get_field_by_key(self, key: str, field: str) -> Optional[str]:
        """Retrieve a specific field by citation key.

        Args:
            key: Citation key
            field: Field name

        Returns:
            Field value if found, None otherwise
        """
