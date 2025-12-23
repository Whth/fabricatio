"""Synthesizes data based on the provided prompt and returns it as a DataFrame."""

from typing import Any

import pandas as pd
from fabricatio_core import Action, Task
from fabricatio_core.utils import ok

from fabricatio_plot.capabilities.synthesize_data import SynthesizeData


class MakeSynthesizedData(Action, SynthesizeData):
    """Action to synthesize data using synthesize data capabilities."""

    output_key: str = "synthesized_data"

    async def _execute(self, task_input: Task, *_: Any, **cxt) -> pd.DataFrame:
        return ok(await self.synthesize_data(task_input.assembled_prompt))
