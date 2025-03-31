"""Some necessary instances."""

from fabricatio.config import configs
from fabricatio.rust import TemplateManager

TEMPLATE_MANAGER = TemplateManager(
    template_dirs=configs.templates.template_dir,
    suffix=configs.templates.template_suffix,
    active_loading=configs.templates.active_loading,
)
