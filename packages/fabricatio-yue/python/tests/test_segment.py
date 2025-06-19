"""Test module for Segment and Song class functionality.

This module contains unit tests for the Segment and Song classes,
covering lyric assembly, genre management, duration calculation,
and file output operations.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List

import pytest
from fabricatio_yue.models.segment import Segment, Song

# Parametrized test cases for Segment assembly
test_segment_cases = [
    (
        "Basic section",
        "verse",
        30,
        ["Line 1", "Line 2"],
        ["pop", "rock"],
        "[verse]\nLine 1\nLine 2",
    ),
    (
        "Empty lyrics",
        "chorus",
        45,
        [],
        [],
        "[chorus]\n",
    ),
]


@pytest.mark.parametrize(
    ("description", "section_type", "duration", "lyrics", "genres", "expected"), test_segment_cases
)
def test_segment_assembly(
    description: str,
    section_type: str,
    duration: int,
    lyrics: List[str],
    genres: List[str],
    expected: str,
) -> None:
    """Test that Segment assembly correctly formats section content.

    Args:
        description: Description of test case
        section_type: Type of musical section
        duration: Duration in seconds
        lyrics: List of lyric lines
        genres: Additional genre tags
        expected: Expected assembled string
    """
    segment = Segment(section_type=section_type, duration=duration, lyrics=lyrics).override_extra_genres(genres)
    assert segment.assemble == expected


def test_segment_genres() -> None:
    """Test genre management in Segment class."""
    segment = Segment(section_type="bridge", duration=20, lyrics=["Final lines"]).override_extra_genres(
        ["electronic", "ambient"]
    )

    assert segment.extra_genres == ["electronic", "ambient"]
    segment.override_extra_genres(["jazz"])
    assert segment.extra_genres == ["jazz"]


def test_song_duration() -> None:
    """Test duration calculation in Song class."""
    segments = [
        Segment(section_type="verse", duration=30, lyrics=["a"]).override_extra_genres(["g1"]),
        Segment(section_type="chorus", duration=45, lyrics=["b"]).override_extra_genres(["g2"]),
    ]

    song = Song(name="test", description="test song", genres=["pop"], segments=segments)
    assert song.duration == 75  # 30 + 45


def test_song_genres() -> None:
    """Test genre management in Song class."""
    song = Song(name="test", description="test song", genres=["rock"], segments=[]).override_genres(
        ["metal", "hardcore"]
    )

    assert song.genres == ["metal", "hardcore"]


def test_song_save_to() -> None:
    """Test song saving creates valid files in target directory."""
    segments = [
        Segment(section_type="verse", duration=30, lyrics=["Line 1", "Line 2"]).override_extra_genres(["genre1"]),
        Segment(section_type="chorus", duration=20, lyrics=["Line 3", "Line 4"]).override_extra_genres(["genre2"]),
    ]

    song = Song(name="test_song", description="A test song", genres=["pop"], segments=segments)

    with TemporaryDirectory() as temp_dir:
        result = song.save_to(temp_dir)
        # Verify method returns self for chaining
        assert result is song
        # Verify file exists
        song_file = Path(temp_dir, "test_song.md")
        assert song_file.exists()

        # Verify file content
        content = song_file.read_text(encoding="utf-8")
        assert "# test_song" in content
        assert "> A test song" in content
        assert "Duration: 30 s" in content
        assert "Lyrics" in content
        assert "[verse]" in content
