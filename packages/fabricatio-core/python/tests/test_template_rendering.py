"""Test module for template rendering functionality in TemplateManager.

This module contains pytest test cases for verifying the correctness of template
rendering operations, including template discovery, store management, and both
single and batch template rendering functionalities. Tests cover both successful
execution paths and error handling scenarios.
"""

from pathlib import Path

import pytest
from fabricatio_core.rust import TEMPLATE_MANAGER, TemplateManager


@pytest.fixture
def template_manager() -> TemplateManager:
    """Get the singleton TemplateManager instance for testing."""
    return TEMPLATE_MANAGER


@pytest.fixture
def sample_template_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with sample templates."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()

    # Create a sample template file
    template_file = template_dir / "test_template.hbs"
    template_file.write_text("Hello {{name}}!")

    return template_dir


def test_template_count_property(template_manager: TemplateManager) -> None:
    """Test that template_count returns an integer."""
    count = template_manager.template_count
    assert isinstance(count, int)
    assert count >= 0


def test_add_store_single_directory(template_manager: TemplateManager, sample_template_dir: Path) -> None:
    """Test adding a single template directory."""
    result = template_manager.add_store(sample_template_dir)
    assert result is template_manager  # Should return self for chaining


def test_add_store_with_rediscovery(template_manager: TemplateManager, sample_template_dir: Path) -> None:
    """Test adding a store with rediscovery enabled."""
    result = template_manager.add_store(sample_template_dir, rediscovery=True)
    assert result is template_manager


def test_add_stores_multiple_directories(template_manager: TemplateManager, tmp_path: Path) -> None:
    """Test adding multiple template directories."""
    dir1 = tmp_path / "templates1"
    dir2 = tmp_path / "templates2"
    dir1.mkdir()
    dir2.mkdir()
    result = template_manager.add_stores([dir1, dir2])
    assert result is template_manager


def test_add_stores_with_rediscovery(template_manager: TemplateManager, tmp_path: Path) -> None:
    """Test adding multiple stores with rediscovery enabled."""
    dir1 = tmp_path / "templates1"
    dir2 = tmp_path / "templates2"
    dir1.mkdir()
    dir2.mkdir()

    result = template_manager.add_stores([dir1, dir2], rediscovery=True)
    assert result is template_manager


def test_discover_templates(template_manager: TemplateManager) -> None:
    """Test template discovery."""
    result = template_manager.discover_templates()
    assert result is template_manager  # Should return self for chaining


def test_templates_stores_property(template_manager: TemplateManager) -> None:
    """Test that templates_stores returns a list of Path objects."""
    stores = template_manager.templates_stores
    assert isinstance(stores, list)
    # Each item should be a Path object
    for store in stores:
        assert hasattr(store, "exists")  # Path-like object check


def test_add_store_and_check_stores(template_manager: TemplateManager, sample_template_dir: Path) -> None:
    """Test adding a store and verifying it appears in templates_stores."""
    initial_count = len(template_manager.templates_stores)
    template_manager.add_store(sample_template_dir)

    # Check that the store was added
    stores = template_manager.templates_stores
    assert len(stores) >= initial_count
    assert sample_template_dir in stores


def test_integration_with_real_template(template_manager: TemplateManager, sample_template_dir: Path) -> None:
    """Test template rendering with a real template file."""
    # Add the template directory and discover templates
    template_manager.add_store(sample_template_dir, rediscovery=True)

    result = template_manager.render_template("test_template", {"name": "World"})
    assert isinstance(result, str)
    assert "Hello" in result
    assert "World" in result


def test_render_template_raw_integration(template_manager: TemplateManager) -> None:
    """Test raw template rendering."""
    template_str = "Hello {{name}}!"
    data = {"name": "World"}

    result = template_manager.render_template_raw(template_str, data)
    assert isinstance(result, str)
    assert result == "Hello World!"


def test_render_template_with_list_data(template_manager: TemplateManager) -> None:
    """Test rendering template with list of data."""
    template_str = "Hello {{name}}! You are {{position}} in the queue."
    data = [
        {"name": "World", "position": "first"},
        {"name": "Universe", "position": "second"},
        {"name": "Galaxy", "position": "third"},
        {"name": "Star", "position": "fourth"},
        {"name": "Planet", "position": "fifth"},
        {"name": "Solar System", "position": "sixth"},
        {"name": "Moon", "position": "seventh"},
        {"name": "Comet", "position": "eighth"},
        {"name": "Meteor", "position": "ninth"},
        {"name": "Asteroid", "position": "tenth"},
    ]

    result = template_manager.render_template_raw(template_str, data)
    assert isinstance(result, list)
    assert len(result) == 10
    assert result == [
        "Hello World! You are first in the queue.",
        "Hello Universe! You are second in the queue.",
        "Hello Galaxy! You are third in the queue.",
        "Hello Star! You are fourth in the queue.",
        "Hello Planet! You are fifth in the queue.",
        "Hello Solar System! You are sixth in the queue.",
        "Hello Moon! You are seventh in the queue.",
        "Hello Comet! You are eighth in the queue.",
        "Hello Meteor! You are ninth in the queue.",
        "Hello Asteroid! You are tenth in the queue.",
    ]


def test_render_template_error_handling(template_manager: TemplateManager) -> None:
    """Test that RuntimeError is raised when template rendering fails."""
    template_name = "nonexistent_template"
    data = {"name": "World"}

    with pytest.raises(RuntimeError):
        template_manager.render_template(template_name, data)
