"""Saves a DataFrame to a CSV file at the specified path."""

from pathlib import Path

import pandas as pd
from fabricatio_core import Action, Task
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.utils import ok


class SaveDataCSV(Action, UseLLM):
    """Saves a DataFrame to a CSV file at the specified path."""

    async def _execute(
        self, task_input: Task, data_to_save: pd.DataFrame, save_path: str | Path | None = None, **cxt
    ) -> Path:
        p = Path(
            ok(
                save_path
                or await self.awhich_pathstr(
                    f"{task_input.assembled_prompt}\n\nI have the DataFrame to save now, "
                    f"you need to tell where should I save it according to the task requirement."
                )
            )
        )

        p.parent.mkdir(parents=True, exist_ok=True)

        data_to_save.to_csv(p, index=False)
        return p
