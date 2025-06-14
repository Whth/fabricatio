"""Compose action for creating songs."""

from pathlib import Path

from fabricatio_core.models.action import Action
from fabricatio_core.utils import ok

from fabricatio_yue.capabilities.lyricize import Lyricize
from fabricatio_yue.models.segment import Song


class Compose(Action, Lyricize):
    """Compose a song."""

    async def _execute(self, req: str, output: Path, **cxt) -> Song:
        return ok(await self.lyricize(req)).save_to(output)
