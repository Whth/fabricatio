"""RAG-enhanced novel generation workflows."""

from fabricatio_core.utils import cfg

cfg(feats=["workflows"])
from fabricatio_actions.actions.output import PersistentAll  # noqa: I001
from fabricatio_core import WorkFlow

from fabricatio_novel.actions.novel import (
    AssembleNovelFromComponents,
    DumpNovel,
    GenerateChaptersFromScripts,
    GenerateCharactersFromDraft,
    GenerateNovelDraft,
    GenerateScriptsFromDraftAndCharacters,
    ValidateNovel,
)
from fabricatio_novel.actions.novel_rag import InjectWritingStyleToScript, RetrieveWritingStyles


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
        RetrieveWritingStyles,
        InjectWritingStyleToScript,
        GenerateChaptersFromScripts,
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
        RetrieveWritingStyles,
        PersistentAll,
        InjectWritingStyleToScript,
        PersistentAll,
        GenerateChaptersFromScripts,
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
        RetrieveWritingStyles,
        InjectWritingStyleToScript,
        GenerateChaptersFromScripts,
        AssembleNovelFromComponents,
        ValidateNovel,
        DumpNovel,
        PersistentAll,
    ),
)
"""Production-grade novel generation with RAG and quality validation."""
