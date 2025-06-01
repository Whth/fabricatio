from csv import reader
from pathlib import Path
from typing import List

from fabricatio_core.models.action import Action
from fabricatio_core.models.usages import LLMUsage

from fabricatio_anki.config import anki_config


class EnsureDeckFields(Action,LLMUsage):

    csv_sep:str= ","

    async def _execute(self, csv_file:Path|str, **cxt) -> List[str]:
        with open(csv_file) as f:
            csv_reader = reader(f, delimiter=self.csv_sep)
            header = next(csv_reader)


        return await self.alist_str(
            anki_config.ensure_fields_template,
            {"fields": header, }
        )
