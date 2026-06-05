# `fabricatio-diff`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-diff)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-diff)](https://pypi.org/project/fabricatio-diff/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-diff/week)](https://pepy.tech/projects/fabricatio-diff)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-diff)](https://pepy.tech/projects/fabricatio-diff)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

Intelligent diff-based editing for LLM-driven text transformations. Combines fuzzy line matching, hashline-anchored edits, and LLM-generated search-and-replace operations into a single package.

## Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[diff]
# or
uv pip install fabricatio[diff]
```

For a full installation:

```bash
pip install fabricatio[full]
# or
uv pip install fabricatio[full]
```

## Overview

`fabricatio-diff` provides two complementary layers for text editing:

1. **Rust-accelerated primitive operations** — hashline anchoring, fuzzy line matching, unified diffs, and similarity measurement, exposed via PyO3 bindings.
2. **Python orchestration** — a `Diff` model and `DiffEdit` capability that use LLMs to generate search/replace operations from natural language requirements and apply them with configurable precision.

## Key Components

### `Diff` model

Represents a text transformation as a `search` / `replace` pair with optional line-range anchoring.

```python
from fabricatio_diff.models.diff import Diff

# Pattern-matching diff
d = Diff(search="old text", replace="new text")
result = d.apply(source_text, match_precision=0.9)

# Anchor-based line-range diff (stable against content shifts)
d = Diff.from_anchors(start_anchor="10:a1b2", end_anchor="15:c3d4", replace="new lines")

# Line-number-based range diff
d = Diff.from_line_range(start=10, end=15, replace="new lines")

# Reverse a diff
rev = d.reverse()

# Format content with LINE:HASH anchors for LLM prompt context
hashed = d.format_with_hashes(source_text)
```

### `DiffEdit` capability

Mixin class that delegates diff generation to an LLM via prompt templates. Parses the LLM response for `<<<<SEARCH` / `<<<<REPLACE` blocks and constructs a validated `Diff`.

```python
from fabricatio_diff.capabilities.diff_edit import DiffEdit

class MyAgent(DiffEdit, SomeOtherCapability):
    pass

agent = MyAgent()
result = await agent.diff_edit(source_text, "rename variable x to count")
```

### Rust Primitives (imported from `fabricatio_diff.rust`)

| Function | Description |
|---|---|
| `rate(a, b)` | Normalized Damerau-Levenshtein similarity (0.0–1.0) |
| `match_lines(haystack, needle, precision=0.9)` | Find a fuzzy-matching block of lines |
| `show_diff(a, b)` | Generate a unified diff between two strings |
| `compute_hash(line)` | xxHash-based per-line hash |
| `format_hashes(content, start_line=1)` | Annotate each line with `LINE:HASH` |
| `parse_hashline_anchor(anchor)` | Parse `"42:ab12"` into `(line, hash)` |
| `apply_set_line(content, anchor, new_text)` | Replace one line by anchor |
| `apply_insert_after(content, anchor, text)` | Insert after an anchored line |
| `apply_replace(content, old, new, all=False)` | Simple text substitution |
| `apply_replace_lines(content, start, end, text)` | Replace a range between two anchors |

### Configuration

```python
from fabricatio_diff.config import DiffConfig

# Match precision threshold (1.0 = exact, lower = fuzzier)
diff_config.match_precision = 0.85

# Prompt template for diff generation
diff_config.diff_template = "my/custom/template"
```

The `DiffConfig` dataclass is loaded from the global Fabricatio configuration system under the `"diff"` key.

## Dependencies

- `fabricatio-core` — core interfaces, configuration system, and prompt template manager
- Rust crates: `strsim` (similarity), `similar` (unified diffs), `rho-hashline` (line hashing), `rayon` (parallel search)

## License

MIT — see [LICENSE](../../LICENSE)
