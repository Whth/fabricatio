"""Genre selection capabilities for music composition."""

from typing import List, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.models.usages import LLMUsage
from more_itertools import flatten

from fabricatio_yue.config import yue_config


class SelectGenre(LLMUsage):
    """A capability class for selecting appropriate music genres based on requirements."""

    @overload
    async def select_genre(
        self,
        requirement: str,
        genre_classifier: str,
        genres: List[str],
        **kwargs: Unpack[ValidateKwargs[List[str]]],
    ) -> None | List[str]:
        """Select genres for a single requirement.

        Args:
            requirement: A single requirement string describing the desired music style.
            genre_classifier: The type or category of genres to consider.
            genres: List of available genres to choose from.
            **kwargs: Additional validation parameters.

        Returns:
            List of selected genres or None if no genres match the requirement.
        """
        ...

    @overload
    async def select_genre(
        self,
        requirement: List[str],
        genre_classifier: str,
        genres: List[str],
        **kwargs: Unpack[ValidateKwargs[List[str]]],
    ) -> List[List[str] | None]:
        """Select genres for multiple requirements.

        Args:
            requirement: List of requirement strings describing desired music styles.
            genre_classifier: The type or category of genres to consider.
            genres: List of available genres to choose from.
            **kwargs: Additional validation parameters.

        Returns:
            List of genre selections, where each selection is either a list of genres or None.
        """
        ...

    async def select_genre(
        self,
        requirement: str | List[str],
        genre_classifier: str,
        genres: List[str],
        **kwargs: Unpack[ValidateKwargs[List[str]]],
    ) -> None | List[str] | List[List[str] | None]:
        """Select appropriate music genres based on given requirements.

        This method uses template-based generation to select suitable genres from a provided
        list based on textual requirements and a genre classifier.

        Args:
            requirement: Either a single requirement string or list of requirement strings
                        describing the desired music style or characteristics.
            genre_classifier: The type or category of genres to consider (e.g., "pop", "electronic").
            genres: List of available genres to choose from.
            **kwargs: Additional validation parameters passed to the underlying validation system.

        Returns:
            For single requirement: List of selected genres or None if no match.
            For multiple requirements: List where each element is either a list of genres or None.
        """
        if isinstance(requirement, str):
            return await self.alist_str(
                TEMPLATE_MANAGER.render_template(
                    yue_config.select_genre_template,
                    {"requirement": requirement, "genre_classifier": genre_classifier, "genres": genres},
                ),
                **kwargs,
            )
        if isinstance(requirement, list):
            # Handle list of requirements
            return await self.alist_str(
                TEMPLATE_MANAGER.render_template(
                    yue_config.select_genre_template,
                    [
                        {"requirement": req, "genre_classifier": genre_classifier, "genres": genres}
                        for req in requirement
                    ],
                ),
                **kwargs,
            )
        raise TypeError(f"requirement must be str or List[str], got {type(requirement)}")

    @overload
    async def gather_genres(
        self,
        requirements: str,
        **kwargs: Unpack[ValidateKwargs[List[str]]],
    ) -> None | List[str]:
        """Gather genres for a single requirement.

        Args:
            requirements: A single requirement string describing the desired music style.
            **kwargs: Additional validation parameters.

        Returns:
            List of all selected genres from all categories or None if no match.
        """
        ...

    @overload
    async def gather_genres(
        self,
        requirements: List[str],
        **kwargs: Unpack[ValidateKwargs[List[str]]],
    ) -> List[List[str] | None]:
        """Gather genres for multiple requirements.

        Args:
            requirements: List of requirement strings describing desired music styles.
            **kwargs: Additional validation parameters.

        Returns:
            List where each element corresponds to gathered genres for each requirement.
        """
        ...

    async def gather_genres(
        self,
        requirements: str | List[str],
        **kwargs: Unpack[ValidateKwargs[List[str]]],
    ) -> None | List[str] | List[List[str] | None]:
        """Gather genres from all available genre categories based on requirements.

        This method iterates through all genre categories in the configuration and selects
        appropriate genres for each category based on the given requirements.

        Args:
            requirements: Either a single requirement string or list of requirement strings.
            **kwargs: Additional validation parameters.

        Returns:
            For single requirement: List of all selected genres from all categories or None.
            For multiple requirements: List where each element corresponds to gathered genres for each requirement.
        """
        import asyncio

        async def gather_for_single_requirement(req: str) -> List[str] | None:
            """Gather genres for a single requirement from all categories."""
            results = await asyncio.gather(
                *[
                    self.select_genre(req, genre_classifier, genres, **kwargs)
                    for genre_classifier, genres in yue_config.genre.items()
                ]
            )
            # Flatten the results from all genre categories, filtering out any None responses
            selected_genres = list(flatten(result for result in results if result))
            return selected_genres if selected_genres else None

        if isinstance(requirements, str):
            return await gather_for_single_requirement(requirements)
        if isinstance(requirements, list):
            tasks = [gather_for_single_requirement(req) for req in requirements]
            return await asyncio.gather(*tasks)
        raise TypeError(f"requirements must be str or List[str], got {type(requirements)}")
