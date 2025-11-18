# `fabricatio-locale`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-locale)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-locale)](https://pypi.org/project/fabricatio-locale/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-locale/week)](https://pepy.tech/projects/fabricatio-locale)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-locale)](https://pepy.tech/projects/fabricatio-locale)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

An extension of fabricatio, which brings up the capability to generate localization based on PO file.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[locale]
# or
uv pip install fabricatio[locale]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides localization capabilities for fabricatio applications, enabling the translation and adaptation of text content
for different languages and regions using PO file standards. It facilitates seamless internationalization workflows in
AI-driven content creation and processing.

## 🧩 Key Features

- **PO File Processing**: Parse and process standard gettext PO files for localization
- **Message Translation**: Translate message texts while preserving identifiers and context
- **Batch Localization**: Handle multiple messages simultaneously for efficient processing
- **Translation Integration**: Leverages advanced translation capabilities for accurate localization
- **Format Preservation**: Maintains message structure and metadata during translation
- **Internationalization Support**: Enables global content adaptation for diverse audiences

## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
- `fabricatio-translate` - Translation capabilities

No additional dependencies required.

## 📄 License

MIT – see [LICENSE](../../LICENSE)

