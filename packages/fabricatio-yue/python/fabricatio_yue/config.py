"""Module containing configuration classes for fabricatio-yue."""

from pathlib import Path
from typing import Dict, List

from fabricatio_core import CONFIG
from fabricatio_core.decorators import once
from pydantic import BaseModel, ConfigDict, Field
from ujson import load

genres_path = Path(__file__).parent / "top_200_tags.json"


class YueConfig(BaseModel):
    """Configuration for fabricatio-yue."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    segment_types: List[str] = Field(
        default_factory=lambda: ["verse", "chorus", "bridge", "intro", "outro", "solo", "beat", "end"]
    )
    """List of valid segment types for music composition."""

    genre: Dict[str, List[str]] = Field(default_factory=once(lambda: load(genres_path.open())))
    """Dictionary mapping genre categories to lists of specific genres."""

    lyricize_template: str = "lyricize"
    """Template name for lyric generation."""
    select_genre_template: str = "select_genre"
    """Template name for genre selection."""


yue_config = CONFIG.load("yue", YueConfig)
__all__ = ["yue_config"]
