# `fabricatio-translate`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Whth/fabricatio/blob/master/LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-translate)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-translate)](https://pypi.org/project/fabricatio-translate/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-translate/week)](https://pepy.tech/projects/fabricatio-translate)

LLM-powered text translation capability for Fabricatio agents. Supports single
and batch translation with chunked processing for large texts.

## Installation

```bash
pip install fabricatio[translate]
# or
uv pip install fabricatio[translate]
```

## Architecture

The package provides a single capability mixin (`Translate`) that layers into a
Fabricatio `Role`:

| Layer | Class | Purpose |
|-------|-------|---------|
| Capability | `Translate` | Mixin that adds `translate` and `translate_chunked` methods |
| Config | `TranslateConfig` | Template selection (loaded from `fabricatio.toml` under `[translate]`) |

## Usage

Mix `Translate` into a Role to get translation methods:

```python
import asyncio
from fabricatio import Role
from fabricatio_translate.capabilities.translate import Translate

class TranslatorRole(Role, Translate):
    """Role with translation capability."""

async def main() -> None:
    role = TranslatorRole()

    # Single text
    result = await role.translate("Hello, world.", target_language="fr")
    print(result)  # "Bonjour, le monde."

    # Batch translation
    results = await role.translate(["Hello", "Goodbye"], target_language="de")
    print(results)  # ["Hallo", "Auf Wiedersehen"]

    # Chunked translation for long text (splits by word count)
    long_text = "A very long paragraph..." * 1000
    result = await role.translate_chunked(long_text, target_language="ja", chunk_size=4000)

    # With custom specification
    result = await role.translate(
        "The quick brown fox",
        target_language="zh",
        specification="Use formal register. Preserve animal names.",
    )

asyncio.run(main())
```

### Fallback behavior

If an individual translation fails, the source text is preserved in the output
list rather than raising an exception. The utility `fill_empty` handles this
gap-filling:

```python
from fabricatio_translate.capabilities.translate import fill_empty

result = fill_empty(["a", "b", "c"], ["translated_a", None, None])
# result == ["translated_a", "b", "c"]
```

## API Reference

### `Translate` capability

| Method | Returns | Description |
|--------|---------|-------------|
| `translate(text, target_language, specification="", **kwargs)` | `str \| list[str]` | Translate a single text or list of texts |
| `translate_chunked(text, target_language, chunk_size=6000, specification="", **kwargs)` | `str \| list[str]` | Split long text into word-count-based chunks, translate each, and reassemble |

Both methods accept a `specification` string for style, tone, or terminology
instructions passed to the LLM template.

### Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `translate_template` | `"built-in/translate"` | Template key used for translation rendering |

Access at runtime: `from fabricatio_translate import translate_config`

### Kwargs types

| Class | Fields |
|-------|--------|
| `TranslateKwargs` | `target_language: str`, `specification: str` |
| `TranslateChunkedKwargs` | extends `TranslateKwargs` with `chunk_size: int` |

## License

MIT — see the [LICENSE](https://github.com/Whth/fabricatio/blob/master/LICENSE) file.
