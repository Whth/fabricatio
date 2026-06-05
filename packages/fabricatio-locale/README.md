# `fabricatio-locale`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-locale)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-locale)](https://pypi.org/project/fabricatio-locale/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-locale/week)](https://pepy.tech/projects/fabricatio-locale)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-locale)](https://pepy.tech/projects/fabricatio-locale)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv](https://img.shields.io/badge/built%20with-uv-orange)](https://github.com/astral-sh/uv)

Localization extension for Fabricatio. Reads, translates, and writes gettext `.po` files using LLM-powered translation.

---

## Installation

```bash
pip install fabricatio[locale]
# or
uv pip install fabricatio[locale]
```

## Overview

`fabricatio-locale` automates `.po` file localization by combining Rust-backed PO file I/O with Fabricatio's translation pipeline. It parses standard gettext `.po` files, translates message strings to a target language via `fabricatio-translate`, and writes the localized file back — preserving message IDs, metadata, and file structure.

## API

### Rust-backed (PyO3)

| Symbol | Description |
|---|---|
| `Msg(id, txt)` | Immutable message object: `id` is the msgid, `txt` is the translated msgstr. |
| `read_pofile(path)` | Parses a `.po` file and returns `list[Msg]`. |
| `update_pofile(path, messages)` | Writes a sequence of `Msg` back to a `.po` file. |

These are available as `from fabricatio_locale.rust import Msg, read_pofile, update_pofile`.

### Capability

| Class | Description |
|---|---|
| `Localize` | Extends `Translate`. Provides `async localize(msgs: list[Msg], **kwargs) -> list[Msg]` — translates message texts while preserving IDs. |

### Action

| Class | Description |
|---|---|
| `LocalizePoFile` | An executable action combining `Localize` with PO file I/O. Fields: `pofile` (source path), `target_lang` (language code), `output_path` (defaults to overwriting input). Calling `execute()` reads, localizes, and writes the file. |

### Configuration

```python
from fabricatio_locale.config import locale_config
# LocaleConfig is a frozen dataclass loaded from Fabricatio's configuration system.
```

## Usage

```python
from fabricatio_locale.rust import Msg, read_pofile, update_pofile

# Read a PO file
messages = read_pofile("locales/en.po")
for msg in messages:
    print(f"msgid={msg.id} msgstr={msg.txt}")

# Modify and write back
updated = [Msg(id=m.id, txt="translated text") for m in messages]
update_pofile("locales/en.po", updated)
```

```python
from fabricatio_locale.capabilities.localize import Localize

# Localize messages programmatically
class MyLocalizer(Localize):
    pass

localizer = MyLocalizer()
result = await localizer.localize(
    [Msg(id="hello", txt="Hello")],
    target_language="fr"
)
# result[0].txt -> "Bonjour"
```

```python
from fabricatio_locale.actions.localize import LocalizePoFile

# End-to-end PO file localization
action = LocalizePoFile(
    pofile="locales/en.po",
    target_lang="es",
    output_path="locales/es.po"
)
output = await action.execute()
# output: Path("locales/es.po")
```

## Dependencies

- `fabricatio-core` — core interfaces (Action, configuration)
- `fabricatio-translate` — LLM translation pipeline (the `Translate` capability)
- `polib` (Rust) — PO file parsing and writing

## License

MIT — see [LICENSE](LICENSE)
