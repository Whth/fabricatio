from typing import List

from fabricatio_core.models.generic import SketchedAble
from pydantic import NonNegativeInt


class Segment(SketchedAble):
    duration: NonNegativeInt
    extra_genres: List[str]
    lyrics: str = ""


class Song(SketchedAble):
    duration: NonNegativeInt
    genres: List[str]
    segments: List[Segment]
