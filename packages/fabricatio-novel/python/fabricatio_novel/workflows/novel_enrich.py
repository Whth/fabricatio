"""Enrichment workflows for `fabricatio-novel`."""

from fabricatio_core.utils import cfg

cfg(feats=["workflows"])
from fabricatio_core import WorkFlow

from fabricatio_novel.actions.enrich import StoreEnrichedTexts

# ==============================
# 📥 LLM-Enriched Reference Ingestion (Standalone)
# ==============================
StoreEnrichedTextsWorkflow = WorkFlow(
    name="StoreEnrichedTextsWorkflow",
    description=(
        "Ingest text files as LLM-enriched question-answer chunks into LanceDB. "
        "Standalone workflow — not part of novel generation."
    ),
    steps=(StoreEnrichedTexts().to_task_output(),),
)
"""Standalone ingestion workflow for storing LLM-enriched QA chunks derived from source files."""
