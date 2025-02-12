from typing import Any, Dict, List, Self

from pydantic import BaseModel, ConfigDict, DirectoryPath, Field, FilePath, PrivateAttr

from fabricatio.config import configs
from fabricatio.journal import logger


class TemplateManager(BaseModel):
    """A class that manages templates for code generation."""

    model_config = ConfigDict(use_attribute_docstrings=True)
    templates_dir: List[DirectoryPath] = Field(default=configs.code2prompt.template_dir)
    """The directories containing the templates. first element has the highest override priority."""
    _discovered_templates: Dict[str, FilePath] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization method for the model."""
        self.discover_templates()

    def discover_templates(self) -> Self:
        """Discover the templates in the template directories."""
        discovered = [
            f
            for d in self.templates_dir[::-1]
            for f in d.rglob(f"*{configs.code2prompt.template_suffix}", case_sensitive=False)
            if f.is_file()
        ]
        self._discovered_templates = {f.stem: f for f in discovered}
        logger.info(f"Discovered {len(self._discovered_templates)} templates.")
        return self

    def get_template(self, name: str) -> FilePath | None:
        """Get the template with the specified name."""
        return self._discovered_templates.get(name, None)


templates_manager = TemplateManager()
