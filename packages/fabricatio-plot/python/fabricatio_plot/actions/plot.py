"""Make charts using plot capabilities."""

from pathlib import Path
from typing import Any, ClassVar

from fabricatio_core import Action, Task

from fabricatio_plot.capabilities.plot import Plot


class MakeCharts(Action, Plot):
    """Action to create charts using plot capabilities.

    This action combines plotting functionality with task execution to generate
    charts based on provided requirements or prompts.
    """

    ctx_override: ClassVar[bool] = True

    plot_requirement: str | None = None
    """Plot requirement or command."""

    chart_save_path: str | Path | None = None

    async def _execute(self, task_input: Task, *_: Any, **cxt) -> None:
        await self.plot(
            f"{self.plot_requirement or task_input.assembled_prompt}{f'\nYou SHALL save the chart to {self.chart_save_path}' if self.chart_save_path else ''}",
        )
