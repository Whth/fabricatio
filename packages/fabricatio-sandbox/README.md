# `fabricatio-sandbox`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-sandbox)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-sandbox)](https://pypi.org/project/fabricatio-sandbox/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-sandbox/week)](https://pepy.tech/projects/fabricatio-sandbox)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-sandbox)](https://pepy.tech/projects/fabricatio-sandbox)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)



An extension of fabricatio.

---

## 📦 Installation


This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[sandbox]

# or with uv
# uv pip install fabricatio[sandbox]
```

Or install `fabricatio-sandbox` along with all other components of `fabricatio`:

```bash
pip install fabricatio[full]

# or with uv
# uv pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

...



## 🧩 Key Features

...

## Configuration

All options below are read through the fabricatio configuration chain (see the
[Configuration Guide](../../docs/source/configuration.rst)). Set them under the
`[ext.sandbox]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.sandbox]` in `pyproject.toml`, or via
`FABRICATIO_EXT__SANDBOX__<FIELD_UPPER>` environment variables.

```toml
[ext.sandbox]
sandbox_template = "built-in/sandbox"
```

| Option | Type | Default | Description |
|---|---|---|---|
| `sandbox_template` | `str` | `"built-in/sandbox"` | Template name for LLM sandbox prompts. |
| `mounts` | `dict[str, str]` | `{}` | Default mount mapping ``{"/virtual": "/real/path", ...}``. |

Access at runtime: `from fabricatio_sandbox.config import sandbox_config`.

## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
...

## 📄 License

This project is licensed under the MIT License.