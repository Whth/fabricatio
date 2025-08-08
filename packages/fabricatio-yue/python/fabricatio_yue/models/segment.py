"""Models for representing song segments and complete songs.

This module provides the data structures for working with songs and their
component segments in the Fabricatio YUE system. Songs are composed of
multiple segments, each with their own properties like duration, genre tags,
and lyrics.
"""

from pathlib import Path
from typing import List, Self

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.generic import SketchedAble, WithBriefing
from pydantic import Field, NonNegativeInt

from fabricatio_yue.config import yue_config


class Segment(SketchedAble):
    """Represents a segment of a song with its attributes."""

    section_type: str
    """Type of section."""

    duration: NonNegativeInt
    """Duration of the segment in seconds"""
    lyrics: List[str]
    """Lyrics for this segment as a list of lines"""
    extra_genres: List[str] = Field(default_factory=list)
    """Additional genre tags for this segment to control generation if specified."""

    def override_extra_genres(self, genres: List[str]) -> Self:
        """Override the genre tags for this segment.

        Args:
            genres (List[str]): New list of genre tags
        """
        self.extra_genres = genres
        return self

    @property
    def assemble(self) -> str:
        """Assemble the segment into a formatted string representation.

        Returns:
            str: A formatted string with section type header and lyrics
        """
        return f"[{self.section_type}]\n" + "\n".join(self.lyrics)


class Song(SketchedAble, WithBriefing):
    """Represents a complete song with its attributes and segments."""

    genres: List[str]
    """Primary genre classifications for the entire song"""
    segments: List[Segment]
    """Ordered list of segments that compose the song"""

    @property
    def duration(self) -> NonNegativeInt:
        """Total duration of the song in seconds.

        Calculated by summing the durations of all segments in the song.

        Returns:
            NonNegativeInt: The total duration in seconds
        """
        return sum(segment.duration for segment in self.segments)

    def override_genres(self, genres: List[str]) -> Self:
        """Override the primary genre tags for the entire song.

        Args:
            genres (List[str]): New list of genre tags
        """
        self.genres.clear()
        self.genres.extend(genres)
        return self

    def save_to(self, parent_dir: str | Path) -> Self:
        """Save the song to a directory.

        Args:
            parent_dir (str): The directory to save the song to
        """
        parent_path = Path(parent_dir)
        parent_path.mkdir(parents=True, exist_ok=True)

        # Create filename from song name or use default
        file_path = parent_path / f"{self.name}.md"

        logger.info(f"Saving song to {file_path.as_posix()}")

        out = TEMPLATE_MANAGER.render_template(
            yue_config.song_save_template, {"duration": self.duration, **self.model_dump()}
        )
        logger.debug(f"Song content:\n{out}")
        Path(file_path).write_text(out, encoding="utf-8", errors="ignore", newline="\n")

        return self
