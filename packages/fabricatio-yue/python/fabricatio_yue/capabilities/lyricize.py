"""Module containing the Lyricize capability for generating lyrics based on requirements."""

from typing import List, Unpack

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_yue.capabilities.genre import SelectGenre
from fabricatio_yue.config import yue_config
from fabricatio_yue.models.segment import Song


class Lyricize(Propose, SelectGenre):
    """A capability class for generating lyrics based on requirements.

    This class extends the Propose capability to provide lyric generation functionality.
    It supports both single requirement strings and batch processing of multiple requirements.
    Uses the configured lyricize template to generate contextually appropriate lyrics.
    """

    async def lyricize(
            self, requirement: str | List[str], **kwargs: Unpack[ValidateKwargs[Song]]
    ) -> None | Song | List[Song | None]:
        """Generate lyrics based on requirements.

        Args:
            requirement: Single requirement string or list of requirements for lyric generation
            **kwargs: Additional validation kwargs

        Returns:
            Generated lyrics as string, list of strings, or None based on input type
        """
        okwargs = override_kwargs(kwargs, default=None)

        async def lyricize_single(req: str) -> Song | None:
            """Generate a song with lyrics based on a single requirement.
            
            Args:
                req: A single requirement string describing the desired song characteristics.
                
            Returns:
                A Song object containing generated lyrics and metadata, or None if generation fails.
            """
            genres = ok(await self.gather_genres(req, **okwargs))
            prompt = TEMPLATE_MANAGER.render_template(
                yue_config.lyricize_template, {"requirement": req, "genres": genres,"section_types":yue_config.segment_types}
            )
            return await self.propose(Song, prompt, **kwargs)

        if isinstance(requirement, str):
            return await lyricize_single(requirement)

        if isinstance(requirement, list):
            import asyncio
            tasks = [lyricize_single(req) for req in requirement]
            return await asyncio.gather(*tasks)

        raise TypeError(f"Invalid requirement type: {type(requirement)}. Expected str or List[str].")
