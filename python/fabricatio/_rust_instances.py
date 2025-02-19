from fabricatio._rust import TemplateManager
from fabricatio.config import configs

template_manager = TemplateManager(
    template_dirs=configs.templates.template_dir,
    suffix=configs.templates.template_suffix,
    active_loading=configs.templates.active_loading,
)
