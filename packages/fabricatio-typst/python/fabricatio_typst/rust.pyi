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

from typing import List, Optional, Tuple

from pydantic import JsonValue

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

def tex_to_typst(string: str) -> str:
    """Convert TeX to Typst.

    Args:
        string: The input TeX string to be converted.

    Returns:
        The converted Typst string.
    """

def convert_all_tex_math(string: str) -> str:
    r"""Unified function to convert all supported TeX math expressions in a string to Typst format.

    Handles $...$, $$...$$, \\(...\\), and \\[...\\]

    Args:
        string: The input string containing TeX math expressions.

    Returns:
        The string with TeX math expressions converted to Typst format.
    """

def fix_misplaced_labels(string: str) -> str:
    """A func to fix labels in a string.

    Args:
        string: The input string containing misplaced labels.

    Returns:
        The fixed string with labels properly placed.
    """

def comment(string: str) -> str:
    r"""Add comment to the string.

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

def strip_comment(string: str) -> str:
    """Remove leading and trailing comment lines from a multi-line string.

    Args:
        string: Input string that may have comment lines at start and/or end

    Returns:
        str: A new string with leading and trailing comment lines removed
    """

def split_out_metadata(string: str) -> Tuple[Optional[JsonValue], str]:
    """Extracts and parses a YAML metadata block from the beginning of a string.

    The function identifies metadata as a contiguous block of lines at the
    beginning of the input string, where each line must start with `//`.
    The comment prefix (`// ` or `//`) is removed from each of these lines.
    The resulting content, formed by joining these uncommented lines,
    is then parsed as YAML.

    Args:
        string: The input string. If it contains metadata, this metadata must
                be at the very beginning, with each line of the metadata
                block starting with `//`.

    Returns:
        A tuple `(metadata, remaining_string)`:
        - `metadata (Optional[JsonValue])`: The parsed YAML data as a Python object
          (e.g., dict, list) if a valid metadata block was successfully
          identified and parsed. This is `None` if no lines at the start of
          the string begin with `//`, or if the uncommented block is not
          valid YAML.
        - `remaining_string (str)`: The portion of the input string that follows
          the metadata block. If no metadata block was processed (either not
          found or not parsable), this is the original input string.
    """

def to_metadata(data: JsonValue) -> str:
    """Convert a Python object to a YAML string.

    Args:
        data: The Python object to be converted to YAML.

    Returns:
        The YAML string representation of the input data.
    """

def replace_thesis_body(string: str, wrapper: str, new_body: str) -> Optional[str]:
    """Replace content between wrapper strings.

    Args:
        string: The input string containing content wrapped by delimiter strings.
        wrapper: The delimiter string that marks the beginning and end of the content to replace.
        new_body: The new content to place between the wrapper strings.

    Returns:
        A new string with the content between wrappers replaced.

    """

def extract_body(string: str, wrapper: str) -> Optional[str]:
    """Extract the content between two occurrences of a wrapper string.

    Args:
        string: The input string containing content wrapped by delimiter strings.
        wrapper: The delimiter string that marks the beginning and end of the content to extract.

    Returns:
        The content between the first two occurrences of the wrapper string if found, otherwise None.
    """

def extract_sections(string: str, level: int, section_char: str = "#") -> List[Tuple[str, str]]:
    """Extract sections from markdown-style text by header level.

    Args:
        string (str): Input text to parse
        level (int): Header level (e.g., 1 for '#', 2 for '##')
        section_char (str, optional): The character used for headers (default: '#')

    Returns:
        List[Tuple[str, str]]: List of (header_text, section_content) tuples
    """
