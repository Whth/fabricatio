"""Illustrated novel generation workflows.

Chains novel generation with ComfyUI illustration and EPUB export.
"""

from fabricatio_core.utils import cfg

cfg(feats=["workflows"])
from fabricatio_actions.actions.output import PersistentAll
from fabricatio_core import WorkFlow

from fabricatio_novel.actions.illustration import IllustrateNovel
from fabricatio_novel.actions.novel import (
    AssembleNovelFromComponents,
    DumpNovel,
    GenerateChaptersFromScripts,
    GenerateCharactersFromDraft,
    GenerateNovel,
    GenerateNovelDraft,
    GenerateScriptsFromDraftAndCharacters,
    ValidateNovel,
)
from fabricatio_novel.actions.novel_rag import GenerateChaptersFromScriptsWithRAG

# ==============================
# 🎨 Full Illustrated Novel Pipeline (One-Step)
# ==============================
WriteIllustratedNovelWorkflow = WorkFlow(
    name="WriteIllustratedNovelWorkflow",
    description="Generate a novel from outline, illustrate it, and dump to EPUB.",
    steps=(
        GenerateNovel,
        IllustrateNovel,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Generate novel → illustrate → dump to EPUB in one go."""


# ==============================
# 🎨 Illustrated Debug Pipeline (Step-by-step)
# ==============================
DebugIllustratedNovelWorkflow = WorkFlow(
    name="DebugIllustratedNovelWorkflow",
    description="Step-by-step novel generation with illustration for debugging.",
    steps=(
        GenerateNovelDraft,
        PersistentAll,
        GenerateCharactersFromDraft,
        PersistentAll,
        GenerateScriptsFromDraftAndCharacters,
        PersistentAll,
        GenerateChaptersFromScripts,
        PersistentAll,
        AssembleNovelFromComponents,
        PersistentAll,
        IllustrateNovel,
        PersistentAll,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Use this workflow to debug each stage including illustration."""


# ==============================
# 🎨 Illustrate-Only Pipeline (For pre-generated novels)
# ==============================
IllustrateOnlyWorkflow = WorkFlow(
    name="IllustrateOnlyWorkflow",
    description="Illustrate an existing Novel object and dump to EPUB.",
    steps=(
        IllustrateNovel,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Use when a Novel is already generated — only run illustration + dump."""


# ==============================
# 🎨✅ Validated Illustrated Pipeline
# ==============================
ValidatedIllustratedNovelWorkflow = WorkFlow(
    name="ValidatedIllustratedNovelWorkflow",
    description="Generate novel with illustration and quality validation.",
    steps=(
        GenerateNovel,
        ValidateNovel,
        IllustrateNovel,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Production-grade: generate → validate → illustrate → dump."""


# ==============================
# 🎨✍️ RAG + Illustrated Pipelines
# ==============================
WriteRAGIllustratedNovelWorkflow = WorkFlow(
    name="WriteRAGIllustratedNovelWorkflow",
    description="Generate a novel with RAG writing styles, illustrate, and dump to EPUB.",
    steps=(
        GenerateNovelDraft,
        GenerateCharactersFromDraft,
        GenerateScriptsFromDraftAndCharacters,
        GenerateChaptersFromScriptsWithRAG,
        AssembleNovelFromComponents,
        IllustrateNovel,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""RAG writing style injection → illustration → dump."""


DebugRAGIllustratedNovelWorkflow = WorkFlow(
    name="DebugRAGIllustratedNovelWorkflow",
    description="Step-by-step RAG + illustrated novel generation for debugging.",
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
        PersistentAll,
        IllustrateNovel,
        PersistentAll,
        DumpNovel().to_task_output(),
        PersistentAll,
    ),
)
"""Debug each stage of RAG + illustrated pipeline."""
