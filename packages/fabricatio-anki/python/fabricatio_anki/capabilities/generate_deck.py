"""Provide capabilities for creating a deck of cards."""

from asyncio import gather
from typing import List, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_anki.config import anki_config
from fabricatio_anki.models.deck import Deck, Model, ModelMetaData
from fabricatio_anki.models.template import Side, Template
from fabricatio_anki.rust import fname_santitize


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
        **kwargs: Unpack[ValidateKwargs[Deck]],
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

        metadata = await self.propose(
            ModelMetaData,
            TEMPLATE_MANAGER.render_template(
                anki_config.generate_anki_deck_metadata_template, {"requirement": requirement, "fields": fields}
            ),
            **ov_kwargs,
        )

        model_generation_requirements = await self.alist_str(
            TEMPLATE_MANAGER.render_template(
                anki_config.generate_anki_model_generation_requirements_template,
                {"requirement": requirement, "fields": fields},
            ),
            k=km,
            **ov_kwargs,
        )

        models = (
            await self.generate_model(fields, model_generation_requirements, k=kt, **ov_kwargs)
            if model_generation_requirements
            else None
        )

        if models and metadata:
            return Deck(**metadata.as_kwargs(), models=models)
        return kwargs.get("default")

    @overload
    async def generate_model(
        self, fields: List[str], requirement: str, k: int = 0, **kwargs: Unpack[ValidateKwargs[Model]]
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
        self, fields: List[str], requirement: List[str], k: int = 0, **kwargs: Unpack[ValidateKwargs[Model]]
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
        **kwargs: Unpack[ValidateKwargs[Model]],
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
                fname_santitize(
                    ok(
                        await self.ageneric_string(
                            TEMPLATE_MANAGER.render_template(
                                anki_config.generate_anki_model_name_template,
                                {"fields": fields, "requirement": requirement},
                            ),
                            **override_kwargs(kwargs, defualt=None),
                        )
                    )
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

            names = [fname_santitize(ok(name)) for name in names]
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
        self, fields: List[str], requirement: str, **kwargs: Unpack[ValidateKwargs[Template]]
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
        self, fields: List[str], requirement: List[str], **kwargs: Unpack[ValidateKwargs[Template]]
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
        self, fields: List[str], requirement: str | List[str], **kwargs: Unpack[ValidateKwargs[Template]]
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
            return await self._generate_single_template(fields, requirement, **kwargs)
        if isinstance(requirement, list):
            return await self._generate_multiple_templates(fields, requirement, **kwargs)
        raise ValueError("requirement must be a string or a list of strings")

    async def _generate_single_template(
        self, fields: List[str], requirement: str, **kwargs: Unpack[ValidateKwargs[Template]]
    ) -> Template | None:
        """Generate a single template from a string requirement.

        Args:
            fields: Fields used in the template
            requirement: Single requirement for template generation
            **kwargs: Validation keyword arguments

        Returns:
            A single Template instance or None
        """
        okwargs = override_kwargs(kwargs, default=None)

        # Generate template name
        name_rendered = TEMPLATE_MANAGER.render_template(
            anki_config.generate_anki_model_name_template, {"fields": fields, "requirement": requirement}
        )
        name = fname_santitize(ok(await self.ageneric_string(name_rendered, **okwargs)))
        if not name:
            return None

        # Generate front and back sides
        front = await self.generate_front_side(fields, requirement, **okwargs)
        back = await self.generate_back_side(fields, requirement, **okwargs)

        if not front or not back:
            return None

        return Template(name=name, front=front, back=back)

    async def _generate_multiple_templates(
        self, fields: List[str], requirement: List[str], **kwargs: Unpack[ValidateKwargs[Template]]
    ) -> List[Template] | None:
        """Generate multiple templates from a list of requirements.

        Args:
            fields: Fields used in the templates
            requirement: List of requirements for template generation
            **kwargs: Validation keyword arguments

        Returns:
            A list of Template instances or None
        """
        okwargs = override_kwargs(kwargs, default=None)

        # Generate template names
        name_rendered = TEMPLATE_MANAGER.render_template(
            anki_config.generate_anki_model_name_template, [{"fields": fields, "requirement": r} for r in requirement]
        )
        names = ok(await self.ageneric_string(name_rendered, **okwargs))
        if not names:
            return None

        names = [fname_santitize(ok(name)) for name in names]

        # Generate front and back sides for all requirements
        fronts = await self.generate_front_side(fields, requirement, **okwargs)
        backs = await self.generate_back_side(fields, requirement, **okwargs)

        if not fronts or not backs:
            return None

        # Create templates for each requirement
        templates = []
        for name, front, back in zip(names, fronts, backs, strict=False):
            if name and front and back:
                templates.append(Template(name=name, front=front, back=back))

        return templates if templates else None

    async def _generate_side(
        self,
        fields: List[str],
        requirement: str | List[str],
        template_name: str,
        **kwargs: Unpack[ValidateKwargs[Side]],
    ) -> None | Side | List[Side | None]:
        """Generate one or more card sides using the specified template.

        Args:
            fields: Fields used in the side
            requirement: Requirement(s) for side generation
            template_name: Name of the template to use
            **kwargs: Validation keyword arguments

        Returns:
            One or more Side instances based on input type
        """
        if isinstance(requirement, str):
            rendered = TEMPLATE_MANAGER.render_template(template_name, {"fields": fields, "requirement": requirement})
        elif isinstance(requirement, list):
            rendered = TEMPLATE_MANAGER.render_template(
                template_name,
                [{"fields": fields, "requirement": r} for r in requirement],
            )
        else:
            raise ValueError("requirement must be a string or a list of strings")

        okwargs = override_kwargs(kwargs, default=None)

        source_code = ok(await self.acode_string(rendered, "html", **okwargs))
        if not source_code:
            return None

        if isinstance(source_code, str):
            return Side.from_html(source_code)
        return [Side.from_html(code) if code else None for code in source_code]

    @overload
    async def generate_front_side(
        self, fields: List[str], requirement: str, **kwargs: Unpack[ValidateKwargs[Side]]
    ) -> Side | None:
        """Overloaded version for single front side generation.

        Args:
            fields: Fields for the front side
            requirement: Single requirement description
            **kwargs: Validation arguments

        Returns:
            A single Side instance
        """

    @overload
    async def generate_front_side(
        self, fields: List[str], requirement: List[str], **kwargs: Unpack[ValidateKwargs[Side]]
    ) -> List[Side | None] | None:
        """Overloaded version for multiple front side generation.

        Args:
            fields: Fields for the front side
            requirement: List of requirement descriptions
            **kwargs: Validation arguments

        Returns:
            A list of Side instances
        """

    async def generate_front_side(
        self, fields: List[str], requirement: str | List[str], **kwargs: Unpack[ValidateKwargs[Side]]
    ) -> None | Side | List[Side | None]:
        """Generate one or more front sides for Anki cards.

        Args:
            fields: Fields used in the front side
            requirement: Requirement(s) for front side generation
            **kwargs: Validation keyword arguments

        Returns:
            One or more Side instances based on input type
        """
        return await self._generate_side(
            fields, requirement, anki_config.generate_anki_card_front_side_template, **kwargs
        )

    @overload
    async def generate_back_side(
        self, fields: List[str], requirement: str, **kwargs: Unpack[ValidateKwargs[Side]]
    ) -> Side | None:
        """Overloaded version for single back side generation.

        Args:
            fields: Fields for the back side
            requirement: Single requirement description
            **kwargs: Validation arguments

        Returns:
            A single Side instance
        """

    @overload
    async def generate_back_side(
        self, fields: List[str], requirement: List[str], **kwargs: Unpack[ValidateKwargs[Side]]
    ) -> List[Side | None] | None:
        """Overloaded version for multiple back side generation.

        Args:
            fields: Fields for the back side
            requirement: List of requirement descriptions
            **kwargs: Validation arguments

        Returns:
            A list of Side instances
        """

    async def generate_back_side(
        self, fields: List[str], requirement: str | List[str], **kwargs: Unpack[ValidateKwargs[Side]]
    ) -> None | Side | List[Side | None]:
        """Generate one or more back sides for Anki cards.

        Args:
            fields: Fields used in the back side
            requirement: Requirement(s) for back side generation
            **kwargs: Validation keyword arguments

        Returns:
            One or more Side instances based on input type
        """
        return await self._generate_side(
            fields, requirement, anki_config.generate_anki_card_back_side_template, **kwargs
        )
