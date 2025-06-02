"""Provide capabilities for creating a deck of cards."""

from asyncio import gather
from typing import List, Optional, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_anki.config import anki_config
from fabricatio_anki.models.deck import Deck, Model, ModelMetaData
from fabricatio_anki.models.template import Template


class GenerateDeck(Propose):
    """Create a deck of cards with associated models and templates.

    This class provides methods to generate full decks, individual models,
    and card templates based on user requirements and field definitions.
    """

    async def generate_deck(
        self,
        requirement: str,
        fields: List[str],
        km: int = 0,
        kt: int = 0,
        **kwargs: Unpack[ValidateKwargs[Optional[Deck]]],
    ) -> Deck | None:
        """Create a deck with the given name and description.

        Args:
            requirement: The requirement or theme for the deck
            fields: List of fields to be included in the cards
            km: Number of model generation attempts
            kt: Number of template generation attempts
            **kwargs: Additional validation keyword arguments

        Returns:
            A Deck object containing metadata and models
        """
        ov_kwargs = override_kwargs(kwargs, defualt=None)

        metadata = ok(
            await self.propose(
                ModelMetaData,
                TEMPLATE_MANAGER.render_template(
                    anki_config.generate_anki_deck_metadata_template, {"requirement": requirement, "fields": fields}
                ),
                **ov_kwargs,
            )
        )
        model_generation_requirements = ok(
            await self.alist_str(
                TEMPLATE_MANAGER.render_template(
                    anki_config.generate_anki_model_generation_requirements_template,
                    {"requirement": requirement, "fields": fields},
                ),
                k=km,
                **ov_kwargs,
            )
        )

        models = ok(await self.generate_model(fields, model_generation_requirements, k=kt, **ov_kwargs))

        return Deck(**metadata.as_kwargs(), models=models)

    @overload
    async def generate_model(
        self, fields: List[str], requirement: str, k: int = 0, **kwargs: Unpack[ValidateKwargs[Optional[Model]]]
    ) -> Model | None:
        """Overloaded version for single string requirement.

        Args:
            fields: Fields for the model
            requirement: Single requirement description
            k: Number of generation attempts
            **kwargs: Validation arguments

        Returns:
            A single Model instance
        """

    @overload
    async def generate_model(
        self, fields: List[str], requirement: List[str], k: int = 0, **kwargs: Unpack[ValidateKwargs[Optional[Model]]]
    ) -> List[Model] | None:
        """Overloaded version for multiple requirements.

        Args:
            fields: Fields for the model
            requirement: List of requirement descriptions
            k: Number of generation attempts
            **kwargs: Validation arguments

        Returns:
            A list of Model instances
        """

    async def generate_model(
        self,
        fields: List[str],
        requirement: str | List[str],
        k: int = 0,
        **kwargs: Unpack[ValidateKwargs[Optional[Model]]],
    ) -> Model | List[Model] | None:
        """Generate one or more Anki card models.

        Args:
            fields: Fields to be included in the model
            requirement: Requirement(s) for model generation
            k: Number of generation attempts
            **kwargs: Validation keyword arguments

        Returns:
            One or more Model instances based on input type
        """
        if isinstance(requirement, str):
            name = ok(
                await self.ageneric_string(
                    TEMPLATE_MANAGER.render_template(
                        anki_config.generate_anki_model_name_template, {"fields": fields, "requirement": requirement}
                    ),
                    **override_kwargs(kwargs, defualt=None),
                )
            )
            # draft card template generation requirements
            template_generation_requirements = ok(
                await self.alist_str(
                    TEMPLATE_MANAGER.render_template(
                        anki_config.generate_anki_card_template_generation_requirements_template,
                        {"fields": fields, "requirement": requirement},
                    ),
                    k=k,
                    **override_kwargs(kwargs, defualt=None),
                )
            )

            templates = ok(
                await self.generate_template(
                    fields, template_generation_requirements, **override_kwargs(kwargs, defualt=None)
                )
            )

            return Model(name=name, fields=fields, templates=templates)
        if isinstance(requirement, list):
            names = ok(
                await self.ageneric_string(
                    TEMPLATE_MANAGER.render_template(
                        anki_config.generate_anki_model_name_template,
                        [{"fields": fields, "requirement": req} for req in requirement],
                    ),
                    **override_kwargs(kwargs, defualt=None),
                )
            )
            template_generation_requirements_seq = ok(
                await self.alist_str(
                    TEMPLATE_MANAGER.render_template(
                        anki_config.generate_anki_card_template_generation_requirements_template,
                        [{"fields": fields, "requirement": req} for req in requirement],
                    ),
                    k=k,
                    **override_kwargs(kwargs, defualt=None),
                )
            )
            templates_seq = await gather(
                *[
                    self.generate_template(fields, template_reqs, **override_kwargs(kwargs, defualt=None))
                    for template_reqs in template_generation_requirements_seq
                    if template_reqs
                ]
            )

            return [
                Model(name=name, fields=fields, templates=templates)
                for name, templates in zip(names, templates_seq, strict=False)
                if templates and name
            ]

        raise ValueError("requirement must be a string or a list of strings")

    @overload
    async def generate_template(
        self, fields: List[str], requirement: str, **kwargs: Unpack[ValidateKwargs[Optional[Template]]]
    ) -> Template | None:
        """Overloaded version for single template generation.

        Args:
            fields: Fields for the template
            requirement: Single requirement description
            **kwargs: Validation arguments

        Returns:
            A single Template instance
        """

    @overload
    async def generate_template(
        self, fields: List[str], requirement: List[str], **kwargs: Unpack[ValidateKwargs[Optional[Template]]]
    ) -> List[Template] | None:
        """Overloaded version for multiple template generation.

        Args:
            fields: Fields for the template
            requirement: List of requirement descriptions
            **kwargs: Validation arguments

        Returns:
            A list of Template instances
        """

    async def generate_template(
        self, fields: List[str], requirement: str | List[str], **kwargs: Unpack[ValidateKwargs[Optional[Template]]]
    ) -> Template | List[Template] | None:
        """Generate one or more card templates.

        Args:
            fields: Fields used in the template
            requirement: Requirement(s) for template generation
            **kwargs: Validation keyword arguments

        Returns:
            One or more Template instances based on input type
        """
        if isinstance(requirement, str):
            rendered = TEMPLATE_MANAGER.render_template(
                anki_config.generate_anki_card_template_template, {"fields": fields, "requirement": requirement}
            )

        elif isinstance(requirement, list):
            rendered = TEMPLATE_MANAGER.render_template(
                anki_config.generate_anki_card_template_template,
                [{"fields": fields, "requirement": r} for r in requirement],
            )
        else:
            raise ValueError("requirement must be a string or a list of strings")
        return await self.propose(Template, rendered, **kwargs)
