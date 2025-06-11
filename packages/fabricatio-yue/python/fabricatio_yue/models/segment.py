"""Models for representing song segments and complete songs.

This module provides the data structures for working with songs and their
component segments in the Fabricatio YUE system. Songs are composed of
multiple segments, each with their own properties like duration, genre tags,
and lyrics.
"""

from pathlib import Path
from typing import List, Self

from fabricatio_core import logger
from fabricatio_core.models.generic import SketchedAble, WithBriefing
from pydantic import NonNegativeInt, PrivateAttr


class Segment(SketchedAble):
    """Represents a segment of a song with its attributes."""

    section_type: str
    """Type of section."""

    duration: NonNegativeInt
    """Duration of the segment in seconds"""
    lyrics: List[str]
    """Lyrics for this segment as a list of lines"""
    _extra_genres: List[str] = PrivateAttr(default_factory=list)
    """Additional genre tags for this segment"""

    def override_extra_genres(self, genres: List[str]) -> Self:
        """Override the genre tags for this segment.

        Args:
            genres (List[str]): New list of genre tags
        """
        self._extra_genres = genres
        return self

    @property
    def extra_genres(self) -> List[str]:
        """Get the additional genre tags for this segment.

        Returns:
            List[str]: List of genre tags
        """
        return self._extra_genres

    @property
    def assemble(self) -> str:
        """Assemble the segment into a formatted string representation.

        Returns:
            str: A formatted string with section type header and lyrics
        """
        return f"[{self.section_type}]\n" + "\n".join(self.lyrics) + "\n"


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

    @property
    def briefing(self) -> str:
        """Generate a briefing of the song including its genre tags and duration."""
        return f"# {self.name}\n>{self.description}\n\nDuration: {self.duration} s.\n\n{self.block(' '.join(self.genres), 'genres')} \n\n---\n"

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

        out = f"{self.briefing}\n" + "\n".join(
            f"## Section {i}. {seg.section_type.capitalize()}\n\n{self._wrapp(seg)}"
            for i, seg in enumerate(self.segments)
        )

        file_path.write_text(out, encoding="utf-8")

        return self

    def _wrapp(self, segment: Segment) -> str:
        return (
            f"Duration: {segment.duration} s.\n\n"
            + (
                f"Extra Genres: {self.block(' '.join(segment.extra_genres), 'genres')}\n"
                f"Assembled Genres: {self.block(' '.join(self.genres + segment.extra_genres), 'genres')}"
            )
            if segment.extra_genres
            else "" + f"Lyrics:{self.block(segment.assemble, 'lyrics')}"
        )

    @staticmethod
    def block(content: str, lang: str = "text") -> str:
        """Create a markdown code block with the specified language.

        Args:
            content (str): The content to wrap in the code block
            lang (str, optional): The language identifier for syntax highlighting. Defaults to 'text'

        Returns:
            str: A formatted markdown code block
        """
        return f"\n```{lang}\n{content}\n```\n"
