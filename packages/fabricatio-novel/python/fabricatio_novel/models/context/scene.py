from typing import Self

from fabricatio_novel.models.context.base import ChainableContext, ContextBase


class SceneContext(ChainableContext, ContextBase):
    content: str = ""
    previous_content: str = ""

    def set_content(self, content: str) -> Self:
        self.content = content
        return self

    def set_previous_content(self, previous_content: str) -> Self:
        self.previous_content = previous_content
        return self
