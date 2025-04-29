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
from typing import Any, Dict, List, Optional, Tuple, overload

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

    @overload
    def render_template(self, name: str, data: Dict[str, Any]) -> str: ...

    @overload
    def render_template(self, name: str, data: List[Dict[str, Any]]) -> List[str]: ...

    def render_template(self, name: str, data: Dict[str, Any] | List[Dict[str, Any]]) -> str | List[str]:
        """Render a template with context data.

        Args:
            name: Template name (without extension)
            data: Context dictionary or list of dictionaries to provide variables to the template

        Returns:
            Rendered template content as string or list of strings

        Raises:
            RuntimeError: If template rendering fails
        """

    @overload
    def render_template_raw(self, template: str, data: Dict[str, Any]) -> str: ...

    @overload
    def render_template_raw(self, template: str, data: List[Dict[str, Any]]) -> List[str]: ...

    def render_template_raw(self, template: str, data: Dict[str, Any] | List[Dict[str, Any]]) -> str | List[str]:
        """Render a template with context data.

        Args:
            template: The template string
            data: Context dictionary or list of dictionaries to provide variables to the template

        Returns:
            Rendered template content as string or list of strings
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

    def get_cite_key_by_title(self, title: str) -> Optional[str]:
        """Find citation key by exact title match.

        Args:
            title: Full title to search for (case-insensitive)

        Returns:
            Citation key if exact match found, None otherwise
        """

    def get_cite_key_by_title_fuzzy(self, title: str) -> Optional[str]:
        """Find citation key by fuzzy title match.

        Args:
            title: Search term to find in bibliography entries

        Returns:
            Citation key of best matching entry, or None if no good match
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


def split_sentence_bounds(string: str) -> List[str]:
    """Split the string into sentences based on sentence boundaries.

    Args:
        string: The input string to be split.

    Returns:
        A list of sentences extracted from the string.
    """


def split_into_chunks(string: str, max_chunk_size: int, max_overlapping_rate: float = 0.3) -> List[str]:
    """Split the string into chunks of a specified size.

    Args:
        string: The input string to be split.
        max_chunk_size: The maximum size of each chunk.
        max_overlapping_rate: The minimum overlapping rate between chunks.

    Returns:
        A list of chunks extracted from the string.
    """


def word_count(string: str) -> int:
    """Count the number of words in the string.

    Args:
        string: The input string to count words from.

    Returns:
        The number of words in the string.
    """


def is_chinese(string: str) -> bool:
    """Check if the given string is in Chinese."""


def is_english(string: str) -> bool:
    """Check if the given string is in English."""


def is_japanese(string: str) -> bool:
    """Check if the given string is in Japanese."""


def is_korean(string: str) -> bool:
    """Check if the given string is in Korean."""


def is_arabic(string: str) -> bool:
    """Check if the given string is in Arabic."""


def is_russian(string: str) -> bool:
    """Check if the given string is in Russian."""


def is_german(string: str) -> bool:
    """Check if the given string is in German."""


def is_french(string: str) -> bool:
    """Check if the given string is in French."""


def is_hindi(string: str) -> bool:
    """Check if the given string is in Hindi."""


def is_italian(string: str) -> bool:
    """Check if the given string is in Italian."""


def is_dutch(string: str) -> bool:
    """Check if the given string is in Dutch."""


def is_portuguese(string: str) -> bool:
    """Check if the given string is in Portuguese."""


def is_swedish(string: str) -> bool:
    """Check if the given string is in Swedish."""


def is_turkish(string: str) -> bool:
    """Check if the given string is in Turkish."""


def is_vietnamese(string: str) -> bool:
    """Check if the given string is in Vietnamese."""


def tex_to_typst(string: str) -> str:
    """Convert TeX to Typst.

    Args:
        string: The input TeX string to be converted.

    Returns:
        The converted Typst string.
    """


def convert_all_inline_tex(string: str) -> str:
    """Convert all inline TeX code in the string.

    Args:
        string: The input string containing inline TeX code wrapped in $code$.

    Returns:
        The converted string with inline TeX code replaced.
    """


def convert_all_block_tex(string: str) -> str:
    """Convert all block TeX code in the string.

    Args:
        string: The input string containing block TeX code wrapped in $$code$$.

    Returns:
        The converted string with block TeX code replaced.
    """


def fix_misplaced_labels(string: str) -> str:
    """A func to fix labels in a string.

    Args:
        string: The input string containing misplaced labels.

    Returns:
        The fixed string with labels properly placed.
    """


def comment(string: str) -> str:
    """Add comment to the string.

    Args:
        string: The input string to which comments will be added.

    Returns:
        The string with each line prefixed by '// '.
    """


def uncomment(string: str) -> str:
    """Remove comment from the string.

    Args:
        string: The input string from which comments will be removed.

    Returns:
        The string with comments (lines starting with '// ' or '//') removed.
    """


def split_out_metadata(string: str) -> Tuple[Optional[JsonValue], str]:
    """Split out metadata from a string.

    Args:
        string: The input string containing metadata.

    Returns:
        A tuple containing the metadata as a Python object (if parseable) and the remaining string.
    """


def to_metadata(data: JsonValue) -> str:
    """Convert a Python object to a YAML string.

    Args:
        data: The Python object to be converted to YAML.

    Returns:
        The YAML string representation of the input data.
    """


def convert_to_inline_formula(string: str) -> str:
    r"""Convert `$...$` to inline formula `\(...\)` and trim spaces."""


def convert_to_block_formula(string: str) -> str:
    r"""Convert `$$...$$` to block formula `\[...\]` and trim spaces."""


def inplace_update(string: str, wrapper: str, new_body: str) -> Optional[str]:
    """Replace content between wrapper strings.

    Args:
        string: The input string containing content wrapped by delimiter strings.
        wrapper: The delimiter string that marks the beginning and end of the content to replace.
        new_body: The new content to place between the wrapper strings.

    Returns:
        A new string with the content between wrappers replaced.
        
    """


def extract_body(string: str, wrapper: str) -> Optional[str]:
    """
    Extract the content between two occurrences of a wrapper string.

    Args:
        string: The input string containing content wrapped by delimiter strings.
        wrapper: The delimiter string that marks the beginning and end of the content to extract.

    Returns:
        The content between the first two occurrences of the wrapper string if found, otherwise None.
    """
