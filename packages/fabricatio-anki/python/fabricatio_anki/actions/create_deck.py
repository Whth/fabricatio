
from typing import ClassVar

from anyio import Path
from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.models.action import Action
from fabricatio_core.models.usages import LLMUsage

from fabricatio_anki.config import anki_config


class MakeDeckCreationProposal(Action, LLMUsage):
    ctx_override: ClassVar[bool] = True
    csv_sep: str = ","
    csv_file: Path | str
    requirement: str

    async def _execute(self, **cxt) -> str | None:
        async with await Path(self.csv_file).open() as f:
            header = (await f.readline()).split(self.csv_sep)

        return await self.ageneric_string(
            TEMPLATE_MANAGER
            .render_template(
                anki_config.make_deck_creation_proposal_template,
                {
                    "requirement": self.requirement,
                    "fields": header,
                },
            ))
