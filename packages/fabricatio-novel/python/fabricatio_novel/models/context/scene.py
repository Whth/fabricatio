from fabricatio_core.models.generic import Described, Titled
from fabricatio_novel.models.context.base import ContextBase


class SceneContext(Titled, Described, ContextBase):
    content: str = ""
    language: str = ""
    previous_content: str = ""
