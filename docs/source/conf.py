# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "fabricatio"
copyright = "2025, Whth"
author = "Whth"
release = "0.1.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
extensions = [
    "autoapi.extension",
    "sphinx_autodoc_typehints",
    "myst_parser",  # Enable Markdown support
    "sphinx_rtd_theme",  # RTD theme integration
    "sphinx.ext.napoleon",  # Support for Google and NumPy style docstrings
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.todo',
]

templates_path = ["_templates"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]



autoapi_type = "python"
autoapi_dirs = ["../../packages"]
autoapi_options = [
    "members",
    "undoc-members",
]