# `fabricatio-skill`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-skill)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-skill)](https://pypi.org/project/fabricatio-skill/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-skill/week)](https://pepy.tech/projects/fabricatio-skill)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-skill)](https://pepy.tech/projects/fabricatio-skill)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)



An extension of fabricatio.

---

## Installation


This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[skill]

# or with uv
# uv pip install fabricatio[skill]
```

Or install `fabricatio-skill` along with all other components of `fabricatio`:

```bash
pip install fabricatio[full]

# or with uv
# uv pip install fabricatio[full]
```

## Overview

Provides essential tools for:

...



## Key Features

...

## Configuration

All options below are read through the fabricatio configuration chain (see the
Configuration Guide at ../../docs/source/configuration.rst). Set them under the
`[ext.skill]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.skill]` in `pyproject.toml`, or via
`FABRICATIO_EXT__SKILL__<FIELD_UPPER>` environment variables.

```
# fabricatio.toml
[ext.skill]
select_skills_template = "built-in/select_skills"
distill_skills_template = "built-in/distill_skills"
default_skill_dirs = ["skills", "extra/skills"]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `select_skills_template` | `str` | `"built-in/select_skills"` | Template name for the LLM prompt that selects relevant skills from a question. |
| `distill_skills_template` | `str` | `"built-in/distill_skills"` | Template name for the LLM prompt that distills skill content to its essence. |
| `default_skill_dirs` | `List[str]` | `["skills", "extra/skills"]` | Default directories to scan for skill files. |

Access at runtime: `from fabricatio_skill.config import skill_config`.

## Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
...

## License

This project is licensed under the MIT License.
