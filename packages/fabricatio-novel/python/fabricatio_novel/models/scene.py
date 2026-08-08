from typing import Self

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described
from fabricatio_novel.models.context.scene import SceneContext


class Scene(Described, WordCount):
    content: str

    @classmethod
    def from_context(cls, ctx: SceneContext) -> Self: ...
