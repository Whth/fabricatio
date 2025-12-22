"""Plot Module.

This module defines the Plot class, which serves as a handler for managing plot-related operations.
It utilizes various toolboxes to fulfill plotting requirements and provides an asynchronous interface
for handling plot tasks.
"""

from typing import Any, Dict, Optional, Set, Unpack

from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_tool.capabilities.handle import Handle
from fabricatio_tool.models.collector import ResultCollector
from fabricatio_tool.models.tool import ToolBox
from pydantic import Field

from fabricatio_plot.toolboxes.dataframe_curd import data_crud_toolbox
from fabricatio_plot.toolboxes.dataframe_io import data_io_toolbox
from fabricatio_plot.toolboxes.plot import plot_toolbox


class Plot(Handle):
    """A class representing a Plot handler, which manages plot-related operations and toolboxes."""

    toolboxes: Set[ToolBox] = Field(default_factory=lambda: {plot_toolbox, data_crud_toolbox, data_io_toolbox})
    """A set of toolboxes used by the Plot handler, including plot_toolbox and data_toolbox by default."""

    async def plot(
        self,
        requirement: str,
        data: Optional[Dict[str, Any]] = None,
        output_spec: Optional[Dict[str, str]] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> ResultCollector | None:
        """An asynchronous method that initiates a plot operation based on the given requirement and keyword arguments.

        Args:
            requirement (str): A string describing the plot requirement or command.
            data (Optional[Dict[str, Any]]): A dictionary containing data for plotting.
            output_spec (Optional[Dict[str, str]]): A dictionary specifying the output format and location.
            **kwargs (ValidateKwargs[str]): Additional unpacked keyword arguments for customizing the plot operation.

        Returns:
            ResultCollector | None: A ResultCollector instance containing the results of the plot operation,
                or None if not applicable.
        """
        return await self.handle(requirement, data, output_spec, **kwargs)
