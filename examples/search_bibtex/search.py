"""Example of using BibManager."""
from fabricatio import BibManager, logger

b = BibManager("Exported Items.bib")
logger.success(
    b.get_cite_key("A Negative Selection Immune System Inspired Methodology for Fault Diagnosis of Wind Turbines"))
logger.success(
    b.get_cite_key_fuzzy(
        "System Inspired Methodology for Fault"
    )
)
