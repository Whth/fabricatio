import pytest

from fabricatio.templates import TemplateManager


@pytest.fixture
def template_manager():
    return TemplateManager(templates_dir="test_templates")


def test_template_manager_initialization(template_manager):
    assert template_manager.templates_dir == "test_templates"


def test_template_manager_load_template(template_manager):
    template_manager.load_template("test_template")
    assert "test_template" in template_manager.templates


def test_template_manager_get_template(template_manager):
    template_manager.load_template("test_template")
    template = template_manager.get_template("test_template")
    assert template == template_manager.templates["test_template"]


def test_template_manager_remove_template(template_manager):
    template_manager.load_template("test_template")
    template_manager.remove_template("test_template")
    assert "test_template" not in template_manager.templates
