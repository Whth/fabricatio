"""Module containing configuration classes for fabricatio-yue."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from fabricatio_core import CONFIG
from ujson import load

genres_path = Path(__file__).parent / "top_200_tags.json"


@dataclass(frozen=True)
class YueConfig:
    """Configuration for fabricatio-yue."""

    segment_type: List[str] = field(
        default_factory=lambda: ["verse", "chorus", "bridge", "intro", "outro", "solo", "beat", "end"]
    )
    """List of valid segment types for music composition."""

    genre: Dict[str, List[str]] = field(default_factory=lambda: load(genres_path.open()))
    """Dictionary mapping genre categories to lists of specific genres."""

    lyricize_template: str = "lyricize"
    """Template name for lyric generation."""


yue_config = CONFIG.load("yue", YueConfig)
__all__ = ["yue_config"]
