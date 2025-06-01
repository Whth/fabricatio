from typing import List

from fabricatio_core.models.generic import Named, SketchedAble

from fabricatio_anki.models.card_type import CardType


class Template(SketchedAble,Named):
    """Template model."""

    card_types:List[CardType]

