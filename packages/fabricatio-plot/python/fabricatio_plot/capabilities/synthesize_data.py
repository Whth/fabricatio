"""Module for synthesizing data using LLM capabilities in a concurrent and batched manner."""

from abc import ABC
from io import StringIO
from typing import TYPE_CHECKING, List, Optional, Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.usages import UseLLM
from fabricatio_core.models.kwargs_types import ListStringKwargs, ValidateKwargs
from fabricatio_core.utils import ok

from fabricatio_plot.config import plot_config

if TYPE_CHECKING:
    from pandas import DataFrame


class SynthesizeData(UseLLM, ABC):
    """Abstract base class for synthesizing structured data based on natural language requirements.

    Inherits core functionality from UseLLM and ABC, enabling LLM-driven data generation workflows.
    Provides methods to generate headers, CSV content, and aggregated data batches.
    """

    async def generate_header(
        self, requirement: str | List[str], **kwargs: Unpack[ListStringKwargs]
    ) -> None | List[str] | List[List[str] | None]:
        """Generate appropriate column headers based on the given requirement(s).

        Args:
            requirement: A single or list of natural language descriptions of the required data.
            **kwargs: Additional keyword arguments passed to the underlying LLM processing.

        Returns:
            A list of generated headers matching the input requirement structure,
            or None if generation fails.
        """
        was_str = isinstance(requirement, str)
        if was_str:
            requirement = [requirement]
        rendered = TEMPLATE_MANAGER.render_template(
            plot_config.generate_header_template, [{"requirement": req} for req in requirement]
        )
        header = await self.alist_str(rendered, **kwargs)
        if header is None:
            return None
        return header[0] if was_str else header

    async def generate_csv_data(
        self,
        requirement: str,
        header: Optional[List[str]],
        rows: int = 100,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional["DataFrame"]:
        """Generate CSV-formatted synthetic data matching the specified requirement and header.

        Args:
            requirement: Natural language description of the required dataset characteristics.
            header: Optional list of column names; if not provided, will be auto-generated.
            rows: Number of data rows to generate (default: 100).
            **kwargs: Additional validation-aware keyword arguments for LLM processing.

        Returns:
            A pandas DataFrame containing the synthesized data if successful,
            or None if parsing or generation fails.
        """
        from pandas import read_csv

        true_header = ok(
            header or await self.generate_header(requirement),
            "header not specified and attempts to generate it from the requirement is also failed.",
        )

        raw_csv = await self.acode_string(
            TEMPLATE_MANAGER.render_template(
                plot_config.generate_csv_data_template,
                {"requirement": requirement, "rows": rows, "header": true_header},
            ),
            plot_config.csv_codeblock_lang,
            **kwargs,
        )
        try:
            df = read_csv(StringIO(raw_csv), sep=plot_config.csv_sep, encoding="utf-8")
            if (d_header := df.columns.tolist()) == true_header:
                return df
            logger.warn(f"Header mismatch: {d_header} != {true_header}")
            return None
        except ValueError as e:
            logger.warn(f"Failed to parse CSV: \n{e}")
            return None

    async def synthesize_data(
        self,
        requirement: str,
        header: Optional[List[str]] = None,
        rows: int = 1000,
        batch_size: int = 100,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Optional["DataFrame"]:
        """Synthesize large datasets efficiently by parallel batch generation and concatenation.

        Args:
            requirement: Natural language specification of the desired dataset.
            rows: Total number of rows to generate (default: 1000).
            batch_size: Number of rows per parallel batch (default: 100).
            header: Optional explicit column header list; if omitted, auto-generated.
            **kwargs: Validation-aware keyword arguments passed to LLM processing.

        Returns:
            A unified DataFrame containing all successfully generated data,
            or None if no batches succeed.
        """
        from asyncio import gather

        from pandas import concat

        if rows <= 0:
            logger.warn("Row count must be greater than 0.")
            return None

        # Calculate batch sizes upfront
        batch_sizes = []
        for i in range(0, rows, batch_size):
            batch_sizes.append(min(batch_size, rows - i))

        # Generate all batches concurrently
        batch_results = await gather(
            *[
                self.generate_csv_data(
                    f"{requirement}\n\nthis is the [{i}\\{len(batch_sizes)}] batch", header, batch_rows, **kwargs
                )
                for i, batch_rows in enumerate(batch_sizes)
            ]
        )

        # Filter out None results with warning
        batches = []
        for idx, df in enumerate(batch_results):
            if df is None:
                logger.warn(f"Failed to generate batch {idx + 1}.")
            else:
                batches.append(df)

        if not batches:
            return None

        return concat(batches, ignore_index=True)
