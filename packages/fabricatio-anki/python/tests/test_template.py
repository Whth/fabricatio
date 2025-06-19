"""Test module for Template class functionality.

This module contains unit tests for the Template class and its components,
including Side assembly, HTML parsing, inheritance structure, and file saving
behavior.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fabricatio_anki.models.template import Side, Template

# Parametrized test cases for Side assembly
test_side_cases = [
    (
        "Basic side",
        "<p>Content</p>",
        "console.log('test');",
        ".card { color: red; }",
        "<p>Content</p>\n<script>console.log('test');</script>\n<style>.card { color: red; }</style>",
    ),
    (
        "Empty content",
        "",
        "",
        "",
        "\n<script></script>\n<style></style>",
    ),
]


@pytest.mark.parametrize(("description", "layout", "js", "css", "expected"), test_side_cases)
def test_side_assembly(
    description: str,
    layout: str,
    js: str,
    css: str,
    expected: str,
) -> None:
    """Test that Side assembly correctly combines HTML, JS, and CSS components.

    Args:
        description: Description of test case
        layout: HTML layout content
        js: JavaScript code
        css: CSS styles
        expected: Expected assembled output
    """
    side = Side(layout=layout, js=js, css=css)
    assert side.assemble() == expected


test_side_from_html_cases = [
    (
        "Basic HTML content",
        "<div>Question</div><script>console.log('card');</script><style>.card { font-size: 16px; }</style>",
        "<div>Question</div>",
        "console.log('card');",
        ".card { font-size: 16px; }",
    ),
    ("Empty HTML content", "", "", "", ""),
    (
        "HTML with multiple tags",
        "<p>Content</p><script>alert('test');</script><style>.test { color: blue; }</style>",
        "<p>Content</p>",
        "alert('test');",
        ".test { color: blue; }",
    ),
]


@pytest.mark.parametrize(
    ("description", "html_content", "expected_layout", "expected_js", "expected_css"), test_side_from_html_cases
)
def test_side_from_html(
    description: str,
    html_content: str,
    expected_layout: str,
    expected_js: str,
    expected_css: str,
) -> None:
    """Test HTML parsing creates valid Side instances with different HTML content scenarios."""
    side = Side.from_html(html_content)
    assert isinstance(side, Side)
    assert side.layout == expected_layout
    assert side.js == expected_js
    assert side.css == expected_css


test_save_cases = [
    (
        "Basic template",
        "Front content",
        "front.js",
        "front.css",
        "Back content",
        "back.js",
        "back.css",
        "test_template",
    ),
    ("Empty content", "", "", "", "", "", "", "empty_template"),
]


@pytest.mark.parametrize(
    ("description", "front_layout", "front_js", "front_css", "back_layout", "back_js", "back_css", "template_name"),
    test_save_cases,
)
def test_template_save_to(
    description: str,
    front_layout: str,
    front_js: str,
    front_css: str,
    back_layout: str,
    back_js: str,
    back_css: str,
    template_name: str,
) -> None:
    """Test template saving creates valid files in target directory.

    Args:
        description: Description of test case
        front_layout: Front side HTML layout
        front_js: Front side JavaScript
        front_css: Front side CSS
        back_layout: Back side HTML layout
        back_js: Back side JavaScript
        back_css: Back side CSS
        template_name: Name of the template
    """
    front = Side(layout=front_layout, js=front_js, css=front_css)
    back = Side(layout=back_layout, js=back_js, css=back_css)
    template = Template(front=front, back=back, name=template_name)

    with TemporaryDirectory() as temp_dir:
        result = template.save_to(temp_dir)
        # Verify method returns self for chaining
        assert result is template
        # Verify files exist
        template_root = Path(temp_dir) / template.name

        assert Path(template_root / "front.html").exists()
        assert Path(template_root / "back.html").exists()
