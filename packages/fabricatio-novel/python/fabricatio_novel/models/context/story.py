from pydantic import Field

from fabricatio_novel.models.context.base import ContextBase
from fabricatio_novel.models.context.scene import SceneContext


class StoryContext(ContextBase):
    scene_context: list[SceneContext] = Field(default_factory=list)
