"""RAG + state consistency-enhanced novel generation workflows."""

from fabricatio_core.utils import cfg

cfg(feats=["workflows"])
from fabricatio_actions.actions.output import PersistentAll  # noqa: I001
from fabricatio_core import WorkFlow

from fabricatio_novel.actions.illustration import IllustrateNovel
from fabricatio_novel.actions.novel import (
    AssembleNovelFromComponents,
    DumpNovel,
    GenerateCharactersFromDraft,
    GenerateNovelDraft,
    GenerateScriptsFromDraftAndCharacters,
    ValidateNovel,
)
from fabricatio_novel.actions.novel_state_rag import (
    GenerateChaptersFromScriptsWithStateRAG,
    GenerateNovelStateRAG,
)


# ==============================
# ✍️ RAG + State Full Novel Generation
# ==============================
WriteNovelWithStateRAGWorkflow = WorkFlow(
    name="WriteNovelWithStateRAGWorkflow",
    description="Generate and dump a novel with RAG writing style injection + character state consistency.",
    steps=(
        GenerateNovelStateRAG,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Generate a novel from outline with RAG writing styles + state consistency and dump to file."""


# ==============================
# 🧩 RAG + State Debug Workflow (Step-by-step with persistence)
# ==============================
DebugNovelWithStateRAGWorkflow = WorkFlow(
    name="DebugNovelWithStateRAGWorkflow",
    description="Step-by-step novel generation with RAG + state consistency for inspection and debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScriptsWithStateRAG,
        PersistentAll,
        AssembleNovelFromComponents,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Use this workflow to debug each stage of RAG + state-consistent novel generation."""


# ==============================
# ✅ RAG + State Validated Pipeline (Production-grade)
# ==============================
ValidatedNovelWithStateRAGWorkflow = WorkFlow(
    name="ValidatedNovelWithStateRAGWorkflow",
    description="Generate novel with RAG writing styles + state consistency and post-generation validation.",
    steps=(
        GenerateNovelStateRAG,
        ValidateNovel,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Production-grade novel generation with RAG writing styles + state consistency and quality validation."""


# ==============================
# ✍️🧩🎨 RAG + State + Illustrated Pipeline
# ==============================
DebugStateRAGIllustratedNovelWorkflow = WorkFlow(
    name="DebugStateRAGIllustratedNovelWorkflow",
    description="Step-by-step RAG + state-consistency novel generation with illustration for debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScriptsWithStateRAG,
        PersistentAll,
        AssembleNovelFromComponents,
        PersistentAll,
        IllustrateNovel,
        PersistentAll,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Debug each stage of RAG + state-consistency + illustrated pipeline."""
