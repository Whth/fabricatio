"""RAG-enhanced novel generation workflows."""

from fabricatio_core.utils import cfg

cfg(feats=["workflows"])
from fabricatio_actions.actions.output import PersistentAll  # noqa: I001
from fabricatio_core import WorkFlow

from fabricatio_novel.actions.novel import (
    AssembleNovelFromComponents,
    DumpNovel,
    GenerateCharactersFromDraft,
    GenerateNovelDraft,
    GenerateScriptsFromDraftAndCharacters,
    ValidateNovel,
)
from fabricatio_novel.actions.novel_rag import GenerateChaptersFromScriptsWithRAG, StoreWritingStyleTexts


# ==============================
# ✍️ RAG-Enhanced Full Novel Generation
# ==============================
WriteNovelWithRAGWorkflow = WorkFlow(
    name="WriteNovelWithRAGWorkflow",
    description="Generate and dump a novel with RAG writing style injection.",
    steps=(
        GenerateNovelDraft,
        GenerateCharactersFromDraft,
        GenerateScriptsFromDraftAndCharacters,
        GenerateChaptersFromScriptsWithRAG,
        AssembleNovelFromComponents,
        DumpNovel,
        PersistentAll,
    ),
)
"""Generate a novel from outline with RAG writing style augmentation and dump to file."""


# ==============================
# 🧩 RAG Debug Workflow (Step-by-step with persistence)
# ==============================
DebugNovelWithRAGWorkflow = WorkFlow(
    name="DebugNovelWithRAGWorkflow",
    description="Step-by-step novel generation with RAG for inspection and debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScriptsWithRAG,
        PersistentAll,
        AssembleNovelFromComponents,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Use this workflow to debug each stage of RAG-augmented novel generation."""


# ==============================
# ✅ RAG Validated Pipeline (Production-grade)
# ==============================
ValidatedNovelWithRAGWorkflow = WorkFlow(
    name="ValidatedNovelWithRAGWorkflow",
    description="Generate novel with RAG writing styles and post-generation validation.",
    steps=(
        GenerateNovelDraft,
        GenerateCharactersFromDraft,
        GenerateScriptsFromDraftAndCharacters,
        GenerateChaptersFromScriptsWithRAG,
        AssembleNovelFromComponents,
        ValidateNovel,
        DumpNovel,
        PersistentAll,
    ),
)
"""Production-grade novel generation with RAG and quality validation."""


# ==============================
# 📥 Writing Style Reference Ingestion (Standalone)
# ==============================
StoreWritingStyleTextsWorkflow = WorkFlow(
    name="StoreWritingStyleTextsWorkflow",
    description="Ingest plain-text files as writing style references into LanceDB. Standalone workflow — not part of novel generation.",
    steps=(StoreWritingStyleTexts().to_task_output(),),
)
"""Standalone ingestion workflow for adding writing style reference data."""
