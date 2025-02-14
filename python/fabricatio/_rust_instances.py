from fabricatio._rust import TemplateManager

from fabricatio.config import configs

template_manager = TemplateManager(configs.code2prompt.template_dir)
