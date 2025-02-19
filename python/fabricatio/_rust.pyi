from pathlib import Path
from typing import Any, Dict, List, Optional

class TemplateManager:
    """TemplateManager class for managing handlebars templates."""
    def __init__(
        self, template_dirs: List[Path], suffix: Optional[str] = None, active_loading: Optional[bool] = None
    ) -> None:
        """Initialize the template manager.

        Args:
            template_dirs (List[Path]): A list of paths to directories containing templates.
            suffix (str, optional): The suffix of template files. None means 'hbs' suffix.
            active_loading (bool, optional): Whether to enable active loading of templates.
        """

    @property
    def template_count(self) -> int:
        """Get the number of templates discovered."""

    def get_template_source(self, name: str) -> Optional[str]:
        """Get the source path of a template by name.

        Args:
            name (str): The name of the template to retrieve.

        Returns:
            Optional[str]: The source path of the template.
        """

    def discover_templates(self) -> None:
        """Discover templates in the specified directories."""

    def render_template(self, name: str, data: Dict[str, Any]) -> str:
        """Render a template with the given name and data.

        Args:
            name (str): The name of the template to render.
            data (Dict[str, Any]): The data to pass to the template.

        Returns:
            str: The rendered template.
        """

def blake3_hash(content: bytes) -> str:
    """Calculate the BLAKE3 hash of the given data.

    Args:
        content (bytes): The data to hash.

    Returns:
        str: The BLAKE3 hash of the data.
    """
