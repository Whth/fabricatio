from pathlib import Path
from typing import Dict, List, Any


class TemplateManager:
    def __init__(self, template_dirs: List[Path]) -> None:
        """
        Initialize the template manager.
        Args:
            template_dirs (List[Path]): A list of paths to directories containing templates.
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
