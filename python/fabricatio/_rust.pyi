from pathlib import Path
from typing import Any, Dict, List, Optional

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

    def render_template(self, name: str, data: Dict[str, Any]) -> str:
        """Render a template with context data.

        Args:
            name: Template name (without extension)
            data: Context dictionary to provide variables to the template

        Returns:
            Rendered template content as string

        Raises:
            RuntimeError: If template rendering fails
        """


def blake3_hash(content: bytes) -> str:
    """Calculate the BLAKE3 cryptographic hash of data.

    Args:
        content: Bytes to be hashed

    Returns:
        Hex-encoded BLAKE3 hash string
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
