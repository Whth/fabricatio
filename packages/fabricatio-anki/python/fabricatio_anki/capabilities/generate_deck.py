"""Provide capabilities for creating a deck of cards."""
from asyncio import gather
from typing import List, Optional, Unpack, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.utils import ok, override_kwargs

from fabricatio_anki.config import anki_config
from fabricatio_anki.models.deck import Deck, Model
from fabricatio_anki.models.template import Template


class GenerateDeck(Propose):
    """Create a deck of cards."""

    async def generate_deck(self, name: str, description: Optional[str] = None,
                            **kwargs: Unpack[ValidateKwargs[Optional[Deck]]]) -> Deck | None:
        """Create a deck with the given name and description."""
        ...

    @overload
    async def generate_model(self, fields: List[str], requirement: str, k=0,
                             **kwargs: Unpack[ValidateKwargs[Optional[Model]]]) -> Model | None:
        ...

    @overload
    async def generate_model(self, fields: List[str], requirement: List[str], k=0,
                             **kwargs: Unpack[ValidateKwargs[Optional[Model]]]) -> List[Model] | None:
        ...

    async def generate_model(self, fields: List[str],
                             requirement: str | List[str],
                             k=0,
                             **kwargs: Unpack[ValidateKwargs[Optional[Model]]]) -> Model | List[Model] | None:

        if isinstance(requirement, str):
            name = ok(await self.ageneric_string(
                TEMPLATE_MANAGER.render_template(
                    anki_config.generate_anki_model_name_template,
                    {"fields": fields, "requirement": requirement}
                ),
                **override_kwargs(kwargs, defualt=None),
            ))
            # draft card template generation requirements
            template_generation_requirements = ok(await self.alist_str(
                TEMPLATE_MANAGER.render_template(
                    anki_config.generate_anki_card_template_generation_requirements_template,
                    {"fields": fields, "requirement": requirement}
                ),
                k=k,
                **override_kwargs(kwargs, defualt=None),
            ))

            templates = ok(await self.generate_template(fields, template_generation_requirements,
                                                        **override_kwargs(kwargs, defualt=None)))

            return Model(name=name, fields=fields, templates=templates)
        if isinstance(requirement, list):
            names=ok(await self.ageneric_string(
                TEMPLATE_MANAGER.render_template(
                    anki_config.generate_anki_model_name_template,
                    [{"fields": fields, "requirement": req} for req in requirement]

                ),
                **override_kwargs(kwargs, defualt=None),
            ))
            # 由于 alist_str 无法处理批量数据，因此我们使用 gather 来并行执行多个调用
            template_generation_requirements_seq = ok(await self.alist_str(
                TEMPLATE_MANAGER.render_template(
                    anki_config.generate_anki_card_template_generation_requirements_template,
                    [{"fields": fields, "requirement": req} for req in requirement]
                ),
                k=k,
                **override_kwargs(kwargs, defualt=None)
            ))
            templates_seq = await gather(*[self.generate_template(fields, template_reqs,
                                                                  **override_kwargs(kwargs, defualt=None))

                                           for template_reqs in template_generation_requirements_seq if template_reqs
                                           ]
                                         )

            return [Model(name=name, fields=fields, templates=templates) for name,templates in zip(names,templates_seq, strict=False) if templates and name]

        raise ValueError("requirement must be a string or a list of strings")

    @overload
    async def generate_template(self, fields: List[str], requirement: str,
                                **kwargs: Unpack[ValidateKwargs[Optional[Template]]]) -> Template | None:
        ...

    @overload
    async def generate_template(self, fields: List[str], requirement: List[str],
                                **kwargs: Unpack[ValidateKwargs[Optional[Template]]]) -> List[Template] | None:
        ...

    async def generate_template(self, fields: List[str], requirement: str | List[str],
                                **kwargs: Unpack[ValidateKwargs[Optional[Template]]]) -> Template | List[
        Template] | None:

        if isinstance(requirement, str):

            return await self.propose(
                Template,
                TEMPLATE_MANAGER.render_template(
                    anki_config.generate_anki_card_template_template,
                    {"fields": fields, "requirement": requirement}

                ),
                **kwargs,

            )
        if isinstance(requirement, list):
            return await self.propose(
                Template,
                TEMPLATE_MANAGER.render_template(
                    anki_config.generate_anki_card_template_template,
                    [{"fields": fields, "requirement": r} for r in requirement]

                ),
                **kwargs,

            )

        raise ValueError("requirement must be a string or a list of strings")
