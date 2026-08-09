from fabricatio_core.models.generic import Described, Titled
from pydantic import Field
from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.scene import SceneContext


class StoryContext(Titled, Described, ContextBase):
    scene_context: list[SceneContext] = Field(default_factory=list)
