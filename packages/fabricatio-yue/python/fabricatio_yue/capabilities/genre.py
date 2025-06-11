"""Genre selection capabilities for music composition."""

from typing import List, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.journal import logger
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
            requirement (str): A single requirement string describing the desired music style.
            genre_classifier (str): The type or category of genres to consider.
            genres (List[str]): List of available genres to choose from.
            **kwargs (Unpack[ValidateKwargs[List[str]]]): Additional validation parameters.

        Returns:
            None | List[str]: List of selected genres or None if no genres match the requirement.
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
            requirement (List[str]): List of requirement strings describing desired music styles.
            genre_classifier (str): The type or category of genres to consider.
            genres (List[str]): List of available genres to choose from.
            **kwargs (Unpack[ValidateKwargs[List[str]]]): Additional validation parameters.

        Returns:
            List[List[str] | None]: List of genre selections, where each selection is either a list of genres or None.
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
            requirement (str | List[str]): Either a single requirement string or list of requirement strings
                        describing the desired music style or characteristics.
            genre_classifier (str): The type or category of genres to consider (e.g., "pop", "electronic").
            genres (List[str]): List of available genres to choose from.
            **kwargs (Unpack[ValidateKwargs[List[str]]]): Additional validation parameters passed to the underlying validation system.

        Returns:
            None | List[str] | List[List[str] | None]: For single requirement: List of selected genres or None if no match.
            For multiple requirements: List where each element is either a list of genres or None.
        """
        if isinstance(requirement, str):
            logger.debug("Processing single requirement")
            result = await self.alist_str(
                TEMPLATE_MANAGER.render_template(
                    yue_config.select_genre_template,
                    {"requirement": requirement, "genre_classifier": genre_classifier, "genres": genres},
                ),
                **kwargs,
            )
            logger.debug(f"Selected genres for single requirement: {result}")
            return result
        if isinstance(requirement, list):
            logger.debug(f"Processing {len(requirement)} requirements")
            # Handle list of requirements
            result = await self.alist_str(
                TEMPLATE_MANAGER.render_template(
                    yue_config.select_genre_template,
                    [
                        {"requirement": req, "genre_classifier": genre_classifier, "genres": genres}
                        for req in requirement
                    ],
                ),
                **kwargs,
            )
            logger.debug(f"Selected genres for multiple requirements: {result}")
            return result

        error_msg = f"requirement must be str or List[str], got {type(requirement)}"
        logger.error(error_msg)
        raise TypeError(error_msg)

    @overload
    async def gather_genres(
        self,
        requirements: str,
        **kwargs: Unpack[ValidateKwargs[List[str]]],
    ) -> None | List[str]:
        """Gather genres for a single requirement.

        Args:
            requirements (str): A single requirement string describing the desired music style.
            **kwargs (Unpack[ValidateKwargs[List[str]]]): Additional validation parameters.

        Returns:
            None | List[str]: List of all selected genres from all categories or None if no match.
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
            requirements (List[str]): List of requirement strings describing desired music styles.
            **kwargs (Unpack[ValidateKwargs[List[str]]]): Additional validation parameters.

        Returns:
            List[List[str] | None]: List where each element corresponds to gathered genres for each requirement.
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
            requirements (str | List[str]): Either a single requirement string or list of requirement strings.
            **kwargs (Unpack[ValidateKwargs[List[str]]]): Additional validation parameters.

        Returns:
            None | List[str] | List[List[str] | None]: For single requirement: List of all selected genres from all categories or None.
            For multiple requirements: List where each element corresponds to gathered genres for each requirement.
        """
        import asyncio

        logger.debug(f"Gathering genres for requirements: {requirements}")
        logger.debug(f"Available genre categories: {list(yue_config.genre.keys())}")

        async def gather_for_single_requirement(req: str) -> List[str] | None:
            """Gather genres for a single requirement from all categories.

            Args:
                req (str): A single requirement string describing the desired song characteristics.

            Returns:
                List[str] | None: A list of selected genres from all categories, or None if no genres are found.
            """
            logger.debug(f"Gathering genres for single requirement: {req}")

            results = await asyncio.gather(
                *[
                    self.select_genre(req, genre_classifier, genres, **kwargs)
                    for genre_classifier, genres in yue_config.genre.items()
                ]
            )

            logger.debug(f"Raw results from genre selection: {results}")

            # Flatten the results from all genre categories, filtering out any None responses
            selected_genres = list(flatten(result for result in results if result))

            logger.debug(f"Flattened selected genres: {selected_genres}")

            final_result = selected_genres if selected_genres else None
            logger.debug(f"Final result for requirement '{req}': {final_result}")

            return final_result

        if isinstance(requirements, str):
            logger.debug("Processing single requirement string")
            return await gather_for_single_requirement(requirements)
        if isinstance(requirements, list):
            logger.debug(f"Processing {len(requirements)} requirement strings")
            tasks = [gather_for_single_requirement(req) for req in requirements]
            result = await asyncio.gather(*tasks)
            logger.debug(f"Results for all requirements: {result}")
            return result

        error_msg = f"requirements must be str or List[str], got {type(requirements)}"
        logger.error(error_msg)
        raise TypeError(error_msg)
