"""Configuration file for the Sphinx documentation builder."""
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "fabricatio"
copyright = "2025, Whth"
author = "Whth"
release = "0.1.0"
show_authors = True
# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
extensions = [
    "autoapi.extension",
    "sphinx_autodoc_typehints",
    "myst_parser",  # Enable Markdown support
    "sphinx_rtd_theme",  # RTD theme integration
    "sphinx.ext.napoleon",  # Support for Google and NumPy style docstrings
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.graphviz",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinx_togglebutton",
]
# Enable multi-language support
language = "en"  # Default language

# Optional language list (for sphinx-intl)
languages = {
    "en": "English",
    "zh_CN": "简体中文",
}

# Set gettext output directory (where .pot files are generated)
gettext_compact = False  # Generate separate pot files for each document

locale_dirs = ["locales/"]
templates_path = ["_templates"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Modern UI configurations
html_theme_options = {
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
    "style_external_links": True,
    "style_nav_header_background": "#2980b9",
}

# Enable syntax highlighting for code blocks
pygments_style = "sphinx"
pygments_dark_style = "monokai"

# Copy button configuration
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True
copybutton_only_copy_prompt_lines = True
copybutton_remove_prompts = True

# Toggle button configuration
togglebutton_hint = "Click to show/hide"
togglebutton_hint_hide = "Click to hide"

# MyST parser configuration for better markdown support
myst_enable_extensions = [
    "deflist",
    "tasklist",
    "fieldlist",
    "colon_fence",
    "smartquotes",
    "replacements",
    "linkify",
    "strikethrough",
]

# Intersphinx mapping for cross-references
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
}

# Add favicon and logo
html_favicon = "../../assets/logo/400.svg"
html_logo = "../../assets/band.png"
# Additional HTML context
html_context = {
    "display_github": True,
    "github_user": "Whth",
    "github_repo": "fabricatio",
    "github_version": "main/docs/source/",
}

# Show source link
html_show_sourcelink = True
html_show_sphinx = True

autoapi_type = "python"
autoapi_dirs = ["../../packages"]
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "special-members",
]
