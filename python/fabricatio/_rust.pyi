from pathlib import Path
from typing import Dict, List, Any


class TemplateManager:
    def __init__(self, template_dirs: List[Path]) -> None:
        """
        Initialize the template manager.
        Args:
            template_dirs (List[Path]): A list of paths to directories containing templates.
        """

    @property
    def template_count(self) -> int:
        """Get the number of templates discovered."""

    @property
    def templates(self) -> List[str]:
        """Get a list of template names."""

    def get_template(self, name: str) -> str:
        """
        Get a template by name.
        Args:
            name (str): The name of the template to retrieve.

        Returns:
            str: The template content.
        """

    def get_template_source(self, name: str) -> str:
        """
        Get the source path of a template by name.
        Args:
            name (str): The name of the template to retrieve.

        Returns:
            str: The source path of the template.
        """

    def discover_templates(self) -> None:
        """Discover templates in the specified directories."""

    def render_template(self, name: str, data: Dict[str, Any]) -> str:
        """
        Render a template with the given name and data.
        Args:
            name (str): The name of the template to render.
            data (Dict[str, Any]): The data to pass to the template.

        Returns:
            str: The rendered template.
        """
