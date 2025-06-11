"""Module containing the Lyricize capability for generating lyrics based on requirements."""

from typing import List, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.journal import logger
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

    @overload
    async def lyricize(self, requirement: str, **kwargs: Unpack[ValidateKwargs[Song]]) -> Song | None:
        """Generate lyrics for a single requirement.

        Args:
            requirement (str): A single requirement string describing the desired song characteristics
            **kwargs (Unpack[ValidateKwargs[Song]]): Additional validation kwargs

        Returns:
            Song | None: A Song object containing generated lyrics and metadata, or None if generation fails
        """
        ...

    @overload
    async def lyricize(self, requirement: List[str], **kwargs: Unpack[ValidateKwargs[Song]]) -> List[Song | None]:
        """Generate lyrics for multiple requirements.

        Args:
            requirement (List[str]): List of requirement strings for batch lyric generation
            **kwargs (Unpack[ValidateKwargs[Song]]): Additional validation kwargs

        Returns:
            List[Song | None]: List of Song objects or None values corresponding to each requirement
        """
        ...

    async def lyricize(
        self, requirement: str | List[str], **kwargs: Unpack[ValidateKwargs[Song]]
    ) -> Song | None | List[Song | None]:
        """Generate lyrics based on requirements.

        Args:
            requirement (str | List[str]): Single requirement string or list of requirements for lyric generation
            **kwargs (Unpack[ValidateKwargs[Song]]): Additional validation kwargs

        Returns:
            Song | None | List[Song | None]: Generated lyrics as Song object, list of Song objects, or None based on input type
        """
        logger.debug(f"Lyricizing requirements: {requirement}")
        okwargs = override_kwargs(kwargs, default=None)

        async def lyricize_single(req: str) -> Song | None:
            """Generate a song with lyrics based on a single requirement.

            Args:
                req (str): A single requirement string describing the desired song characteristics.

            Returns:
                Song | None: A Song object containing generated lyrics and metadata, or None if generation fails.
            """
            logger.debug(f"Processing single lyricize requirement: {req}")
            genres = ok(await self.gather_genres(req, **okwargs))
            logger.debug(f"Gathered genres for requirement: {genres}")

            prompt = TEMPLATE_MANAGER.render_template(
                yue_config.lyricize_template,
                {"requirement": req, "genres": genres, "section_types": yue_config.segment_types},
            )
            logger.debug(f"Generated prompt for lyricize: {prompt}")

            return await self.propose(Song, prompt, **kwargs)

        if isinstance(requirement, str):
            logger.debug("Processing single requirement string")
            return await lyricize_single(requirement)

        if isinstance(requirement, list):
            logger.debug(f"Processing {len(requirement)} requirement strings")
            import asyncio

            tasks = [lyricize_single(req) for req in requirement]
            return await asyncio.gather(*tasks)

        error_msg = f"Invalid requirement type: {type(requirement)}. Expected str or List[str]."
        logger.error(error_msg)
        raise TypeError(error_msg)
