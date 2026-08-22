# `fabricatio-yue`

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-yue)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-yue)](https://pypi.org/project/fabricatio-yue/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-yue/week)](https://pepy.tech/projects/fabricatio-yue)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-yue)](https://pepy.tech/projects/fabricatio-yue)

AI-powered lyrics composition for music generation with [YuE](https://github.com/multimodal-art-projection/YuE). Provides genre selection, structured lyric generation, and batch song composition integrated into the Fabricatio agent framework.

## Installation

```bash
pip install fabricatio[yue]
```

Or with the CLI extras:

```bash
pip install fabricatio[yue,cli]
```

## Overview

`fabricatio-yue` generates complete song lyrics with genre-appropriate structure (verse, chorus, bridge, etc.). It selects suitable genres from a taxonomy of 200+ tags across five categories — **genre**, **instrument**, **mood**, **gender**, **timbre** — and feeds them into LLM-driven lyric generation. Songs are saved as Markdown files with embedded metadata.

## Key Components

### Models

| Class | Description |
|-------|-------------|
| `Segment` | A song section with `section_type` (verse, chorus, bridge, intro, outro, etc.), `duration` in seconds, `lyrics` as lines, and optional `extra_genres`. `assemble` property formats it as `[section_type]\nlyrics`. |
| `Song` | A complete song with `name`, `description`, `genres`, and an ordered list of `Segment`s. Computes total `duration` from segments. `save_to(path)` writes it as a Markdown file. |

### Capabilities

| Class | Description |
|-------|-------------|
| `SelectGenre` | Selects genres from a category based on text requirements. `select_genre(req, classifier, genres)` picks matching genres; `gather_genres(req)` iterates all categories and returns the combined results. |
| `Lyricize` | Extends `Propose` and `SelectGenre`. `lyricize(requirement)` gathers genres, renders a prompt template, and returns a `Song` object. Accepts a single string or a list for batch generation. |

### Actions

| Class | Description |
|-------|-------------|
| `Compose` | Full pipeline action: `_execute(req, output)` calls `lyricize()` then `save_to(output)`. Usable in a `WorkFlow` step. |

### CLI

```bash
yuek compose -r "an upbeat pop song about summer" -o ./output
```

## Usage

```python
from fabricatio_core import Event, Role, Task, WorkFlow
from fabricatio_yue.actions.compose import Compose

ns = "compose"
Role.with_bio(name="composer").subscribe(
    Event.quick_instantiate(ns),
    WorkFlow(steps=(Compose().to_task_output(),))
).dispatch()

Task(name="compose song").update_init_context(
    req="a melancholic jazz ballad",
    output="./songs",
).delegate_blocking(ns)
```

Using the `Lyricize` capability directly:

```python
from fabricatio_yue.capabilities.lyricize import Lyricize

lyricizer = Lyricize()
song = await lyricizer.lyricize("a fast punk anthem about resilience")
print(song.model_dump_json(indent=2))
```

Using `SelectGenre`:

```python
from fabricatio_yue.capabilities.genre import SelectGenre

selector = SelectGenre()
genres = await selector.gather_genres("dark atmospheric electronic")
```

Song and Segment model usage:

```python
from fabricatio_yue.models.segment import Segment, Song

segments = [
    Segment(section_type="verse", duration=30, lyrics=["First verse line 1", "First verse line 2"]),
    Segment(section_type="chorus", duration=20, lyrics=["Chorus line 1", "Chorus line 2"]),
]

song = Song(
    name="my_song",
    description="A generated song",
    genres=["electronic", "ambient"],
    segments=segments,
)

song.save_to("./songs")
print(song.duration)  # 50
```

## Dependencies

- `fabricatio-core` — core agent framework
- `more-itertools` — flatten genre results
- `orjson` — fast JSON loading of genre tags
- `pydantic` — data model validation

Optional CLI extras: `questionary`, `typer`.

## Configuration

All options below are read through the fabricatio configuration chain (see the
[Configuration Guide](../../docs/source/configuration.rst)). Set them under the
`[ext.yue]` table in `fabricatio.toml`, equivalently under
`[tool.fabricatio.ext.yue]` in `pyproject.toml`, or via
`FABRICATIO_EXT__YUE__<FIELD_UPPER>` environment variables.

```toml
[ext.yue]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `segment_types` | `List[str]` | `["verse", "chorus", "bridge", "intro", "outro", "solo", "beat", "end"]` | List of valid segment types for music composition. |
| `genre` | `Dict[str, List[str]]` | `(see config.py)` | Dictionary mapping genre categories to lists of specific genres. |
| `lyricize_template` | `str` | `"built-in/lyricize"` | Template name for lyric generation. |
| `select_genre_template` | `str` | `"built-in/select_genre"` | Template name for genre selection. |
| `song_save_template` | `str` | `"built-in/song_save"` | Template name for saving a song. |

Access at runtime: `from fabricatio_yue.config import yue_config`.

## License

MIT — see [LICENSE](../../LICENSE)
