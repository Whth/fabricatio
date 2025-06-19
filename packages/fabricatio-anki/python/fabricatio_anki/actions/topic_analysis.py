"""AppendTopicAnalysis adds topic analysis to a CSV file as a new column."""

from pathlib import Path
from typing import Any, ClassVar

from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_anki.capabilities.generate_analysis import GenerateAnalysis


class AppendTopicAnalysis(Action, GenerateAnalysis):
    """Appends topic analysis results as a new column to a given CSV file."""

    ctx_override: ClassVar[bool] = True

    append_col_name: str = "Topic Analysis"
    """Name of the column where topic analysis will be appended."""

    csv_file: str | Path
    """Path to the CSV file where topic analysis should be applied."""
    output_file: str | Path | None = None
    """Path to the output CSV file. If None, the input file will be overwritten."""
    separator: str = ","
    """Separator used in the CSV file. Default is ','."""

    async def _execute(self, *_: Any, **cxt) -> Path | None:
        """Process the CSV file and append topic analysis as a new column.

        Args:
            *_: Variable positional arguments.
            **cxt: Contextual keyword arguments.

        Returns:
            Path: The path to the modified CSV file.
        """
        p = Path(self.csv_file)

        with p.open() as file:
            lines = file.readlines()
        header = lines[0]
        if self.append_col_name in header:
            logger.warning(f"'{self.append_col_name}' already exists in {p.as_posix()}")
            return p

        data_lines = lines[1:]
        analysis_seq = ok(await self.generate_analysis([f"{header}\n{data}" for data in data_lines]))

        header += self.append_col_name
        new_data_lines = [f"{data},{analysis or ''}" for data, analysis in zip(data_lines, analysis_seq, strict=False)]
        with Path(self.output_file or p).open("w") as file:
            file.writelines([header, *new_data_lines])
        logger.success(f"'{self.append_col_name}' column added to {p.as_posix()}")
        return p
