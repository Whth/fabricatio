from typing import List

from fabricatio_core.models.generic import Named, SketchedAble, WithBriefing

from fabricatio_anki.models.template import Template


class Model(SketchedAble,Named):

    field_names:List[str]

    templates:List[Template]




class Deck(SketchedAble,WithBriefing):

    models:List[Model]






