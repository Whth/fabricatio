"""Models for representing song segments and complete songs.

This module provides the data structures for working with songs and their
component segments in the Fabricatio YUE system. Songs are composed of
multiple segments, each with their own properties like duration, genre tags,
and lyrics.
"""

from typing import List, Self

from fabricatio_core.models.generic import SketchedAble, Named, WithBriefing
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

    @property
    def extra_genres(self) -> List[str]:
        """Get the additional genre tags for this segment.

        Returns:
            List[str]: List of genre tags
        """
        return self._extra_genres


class Song(SketchedAble,WithBriefing):
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