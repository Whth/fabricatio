"""Demonstrates BibManager for searching BibTeX files by title. Shows exact-match lookup (get_cite_key_by_title) and fuzzy search (get_cite_key_fuzzy) for finding citation keys when you only remember part of a title."""

from fabricatio import logger
from fabricatio_core.utils import ok
from fabricatio_typst.rust import BibManager

b = BibManager("Exported Items.bib")
logger.info(
    ok(
        b.get_cite_key_by_title(
            "A Negative Selection Immune System Inspired Methodology for Fault Diagnosis of Wind Turbines"
        )
    )
)
logger.info(ok(b.get_cite_key_fuzzy("System Inspired Methodology for Fault")))
