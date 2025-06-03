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
    "myst_parser",  # 支持 Markdown
    "sphinx_rtd_theme",
    "sphinx.ext.napoleon",  # 支持 Google 和 NumPy 风格的 docstring
]

templates_path = ["_templates"]
exclude_patterns = ["rust.pyi"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]


# 自动解析 Python 包

autoapi_type = "python"
autoapi_dirs = ["../../packages"]
