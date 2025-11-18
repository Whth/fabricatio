# `fabricatio-translate`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-translate)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-translate)](https://pypi.org/project/fabricatio-translate/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-translate/week)](https://pepy.tech/projects/fabricatio-translate)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-translate)](https://pepy.tech/projects/fabricatio-translate)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

An extension of fabricatio, which provides capabilities to translate text.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency using either pip or uv:

```bash
pip install fabricatio[translate]
# or
uv pip install fabricatio[translate]
```

For a full installation that includes this package and all other components of `fabricatio`:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## 🔍 Overview

Provides advanced text translation capabilities for fabricatio agents, supporting both single text and batch translation
operations. It enables seamless multilingual communication with configurable translation specifications and supports
chunked processing for large texts.

## 🧩 Key Features

- **Multi-language Support**: Translate text between various languages with accurate context preservation
- **Batch Processing**: Handle multiple translation requests simultaneously for efficiency
- **Chunked Translation**: Process large texts by splitting them into manageable chunks with proper reassembly
- **Configurable Specifications**: Customize translation style, tone, and terminology through specifications
- **Fallback Handling**: Graceful handling of translation failures with source text preservation
- **Async Processing**: High-performance asynchronous translation operations

## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities

No additional dependencies required.

## 📄 License

MIT – see [LICENSE](../../LICENSE)

