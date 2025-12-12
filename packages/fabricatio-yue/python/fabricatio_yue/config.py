"""Module containing configuration classes for fabricatio-yue."""

from pathlib import Path
from typing import Dict, List

from fabricatio_core import CONFIG
from fabricatio_core.decorators import once
from orjson import loads
from pydantic import BaseModel, ConfigDict, Field

genres_path = Path(__file__).parent / "top_200_tags.json"


class YueConfig(BaseModel):
    """Configuration for fabricatio-yue."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    segment_types: List[str] = Field(
        default_factory=lambda: ["verse", "chorus", "bridge", "intro", "outro", "solo", "beat", "end"]
    )
    """List of valid segment types for music composition."""

    genre: Dict[str, List[str]] = Field(default_factory=once(lambda: loads(genres_path.read_bytes())))
    """Dictionary mapping genre categories to lists of specific genres."""

    lyricize_template: str = "built-in/lyricize"
    """Template name for lyric generation."""
    select_genre_template: str = "built-in/select_genre"
    """Template name for genre selection."""

    song_save_template: str = "built-in/song_save"
    """Template name for saving a song."""


yue_config = CONFIG.load("yue", YueConfig)
__all__ = ["yue_config"]
