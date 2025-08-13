"""AppendTopicAnalysis adds topic analysis to a CSV file as a new column."""

import csv
from pathlib import Path
from typing import Any, ClassVar

from fabricatio_core import Action, logger
from fabricatio_core.utils import ok

from fabricatio_anki.capabilities.generate_analysis import GenerateAnalysis


class AppendTopicAnalysis(Action, GenerateAnalysis):
    """Appends topic analysis results as a new column to a given CSV file.

    This class reads the specified CSV file, generates topic analysis for each row,
    and appends it as a new column. The result is either saved in a new file or
    overwrites the original if no output path is provided.
    """

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

        Reads the CSV file line by line using the `csv` module, generates topic
        analysis for each row, and writes the updated data back to the file or
        to a new file if an output path is specified.

        Args:
            *_: Ignored positional arguments.
            **cxt: Contextual keyword arguments (not used here).

        Returns:
            Path: The path to the modified CSV file.
        """
        input_path = Path(self.csv_file)
        output_path = Path(self.output_file or self.csv_file)

        with input_path.open("r", newline="", encoding="utf-8") as infile:
            reader = csv.DictReader(infile, delimiter=self.separator)
            if not reader.fieldnames:
                raise ValueError(f"CSV file {input_path} is empty or malformed.")
            if self.append_col_name in reader.fieldnames:
                logger.warn(f"'{self.append_col_name}' already exists in {input_path.as_posix()}")
                return input_path

            # Read all rows and prepare for analysis
            rows = list(reader)
            fieldnames = [*list(reader.fieldnames), self.append_col_name]

        # Prepare content per row for analysis
        # Generate analysis asynchronously
        analyses = ok(
            await self.generate_analysis(
                [
                    f"{','.join(fieldnames)}\n{','.join(row.values())}\n"  # Reconstructing line from values
                    for row in rows
                ]
            )
        )

        # Append analysis results to each row
        for row, analysis in zip(rows, analyses, strict=False):
            row[self.append_col_name] = analysis.assemble() if analysis else ""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Write updated rows to the output file
        with output_path.open("w+", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=self.separator)
            writer.writeheader()
            writer.writerows(rows)

        logger.info(f"'{self.append_col_name}' column added to {output_path.as_posix()}")
        return output_path
