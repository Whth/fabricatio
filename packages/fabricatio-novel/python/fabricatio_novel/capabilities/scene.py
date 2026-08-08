from abc import ABC
from typing import Unpack

from fabricatio_character.capabilities.character import CharacterCompose
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.scene import Scene


class SceneCompose(CharacterCompose, ABC):
    """This class contains the capabilities for the scene."""

    async def before_compose_scene(
            self,
            ctx: SceneContext,
            **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext: ...

    async def after_compose_scene(
            self,
            ctx: SceneContext,
            **kwargs: Unpack[LLMKwargs],
    ) -> SceneContext: ...

    async def post_process_scene(self, ctx: SceneContext, scene: Scene, **kwargs: Unpack[LLMKwargs]) -> Scene: ...

    async def generate_scene(
            self,
            ctx: SceneContext,
            send_to: str | None = TASK,
            **kwargs: Unpack[LLMKwargs],
    ) -> Scene | None: ...

    async def compose_scene(
            self,
            ctx: SceneContext,
            send_to: str | None = TASK,
            **kwargs: Unpack[LLMKwargs],
    ) -> Scene | None:
        ctx = await self.before_compose_scene(ctx, **kwargs)
        scene = await self.generate_scene(ctx, send_to, **kwargs)
        ctx = await self.after_compose_scene(ctx, **kwargs)

        if scene is None:
            return None
        ok_scene = await self.post_process_scene(ctx, scene, **kwargs)

        return ok_scene
