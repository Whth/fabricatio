"""Models for representing song segments and complete songs.

This module provides the data structures for working with songs and their
component segments in the Fabricatio YUE system. Songs are composed of
multiple segments, each with their own properties like duration, genre tags,
and lyrics.
"""

from typing import List

from fabricatio_core.models.generic import SketchedAble
from pydantic import NonNegativeInt


class Segment(SketchedAble):
    """Represents a segment of a song with its attributes."""

    duration: NonNegativeInt
    """Duration of the segment in seconds"""
    extra_genres: List[str]
    """Additional genre tags for this segment"""
    lyrics: List[str]
    """Lyrics for this segment as a list of lines"""


class Song(SketchedAble):
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
